# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the ssl key.

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

__virtualname__ = 'ssl'


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

    return False, 'The ssl execution module can only be loaded for citrixns proxy minions.'


def add_sslaction(name=None, clientauth=None, clientcert=None, certheader=None, clientcertserialnumber=None,
                  certserialheader=None, clientcertsubject=None, certsubjectheader=None, clientcerthash=None,
                  certhashheader=None, clientcertfingerprint=None, certfingerprintheader=None,
                  certfingerprintdigest=None, clientcertissuer=None, certissuerheader=None, sessionid=None,
                  sessionidheader=None, cipher=None, cipherheader=None, clientcertnotbefore=None,
                  certnotbeforeheader=None, clientcertnotafter=None, certnotafterheader=None, owasupport=None,
                  save=False):
    '''
    Add a new sslaction to the running configuration.

    name(str): Name for the SSL action. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the action is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my action" or my action). Minimum length = 1

    clientauth(str): Perform client certificate authentication. Possible values = DOCLIENTAUTH, NOCLIENTAUTH

    clientcert(str): Insert the entire client certificate into the HTTP header of the request being sent to the web server.
        The certificate is inserted in ASCII (PEM) format. Possible values = ENABLED, DISABLED

    certheader(str): Name of the header into which to insert the client certificate.

    clientcertserialnumber(str): Insert the entire client serial number into the HTTP header of the request being sent to the
        web server. Possible values = ENABLED, DISABLED

    certserialheader(str): Name of the header into which to insert the client serial number.

    clientcertsubject(str): Insert the client certificate subject, also known as the distinguished name (DN), into the HTTP
        header of the request being sent to the web server. Possible values = ENABLED, DISABLED

    certsubjectheader(str): Name of the header into which to insert the client certificate subject.

    clientcerthash(str): Insert the certificates signature into the HTTP header of the request being sent to the web server.
        The signature is the value extracted directly from the X.509 certificate signature field. All X.509 certificates
        contain a signature field. Possible values = ENABLED, DISABLED

    certhashheader(str): Name of the header into which to insert the client certificate signature (hash).

    clientcertfingerprint(str): Insert the certificates fingerprint into the HTTP header of the request being sent to the web
        server. The fingerprint is derived by computing the specified hash value (SHA256, for example) of the
        DER-encoding of the client certificate. Possible values = ENABLED, DISABLED

    certfingerprintheader(str): Name of the header into which to insert the client certificate fingerprint.

    certfingerprintdigest(str): Digest algorithm used to compute the fingerprint of the client certificate. Possible values =
        SHA1, SHA224, SHA256, SHA384, SHA512

    clientcertissuer(str): Insert the certificate issuer details into the HTTP header of the request being sent to the web
        server. Possible values = ENABLED, DISABLED

    certissuerheader(str): Name of the header into which to insert the client certificate issuer details.

    sessionid(str): Insert the SSL session ID into the HTTP header of the request being sent to the web server. Every SSL
        connection that the client and the NetScaler share has a unique ID that identifies the specific connection.
        Possible values = ENABLED, DISABLED

    sessionidheader(str): Name of the header into which to insert the Session ID.

    cipher(str): Insert the cipher suite that the client and the NetScaler appliance negotiated for the SSL session into the
        HTTP header of the request being sent to the web server. The appliance inserts the cipher-suite name, SSL
        protocol, export or non-export string, and cipher strength bit, depending on the type of browser connecting to
        the SSL virtual server or service (for example, Cipher-Suite: RC4- MD5 SSLv3 Non-Export 128-bit). Possible values
        = ENABLED, DISABLED

    cipherheader(str): Name of the header into which to insert the name of the cipher suite.

    clientcertnotbefore(str): Insert the date from which the certificate is valid into the HTTP header of the request being
        sent to the web server. Every certificate is configured with the date and time from which it is valid. Possible
        values = ENABLED, DISABLED

    certnotbeforeheader(str): Name of the header into which to insert the date and time from which the certificate is valid.

    clientcertnotafter(str): Insert the date of expiry of the certificate into the HTTP header of the request being sent to
        the web server. Every certificate is configured with the date and time at which the certificate expires. Possible
        values = ENABLED, DISABLED

    certnotafterheader(str): Name of the header into which to insert the certificates expiry date.

    owasupport(str): If the appliance is in front of an Outlook Web Access (OWA) server, insert a special header field,
        FRONT-END-HTTPS: ON, into the HTTP requests going to the OWA server. This header communicates to the server that
        the transaction is HTTPS and not HTTP. Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslaction <args>

    '''

    result = {}

    payload = {'sslaction': {}}

    if name:
        payload['sslaction']['name'] = name

    if clientauth:
        payload['sslaction']['clientauth'] = clientauth

    if clientcert:
        payload['sslaction']['clientcert'] = clientcert

    if certheader:
        payload['sslaction']['certheader'] = certheader

    if clientcertserialnumber:
        payload['sslaction']['clientcertserialnumber'] = clientcertserialnumber

    if certserialheader:
        payload['sslaction']['certserialheader'] = certserialheader

    if clientcertsubject:
        payload['sslaction']['clientcertsubject'] = clientcertsubject

    if certsubjectheader:
        payload['sslaction']['certsubjectheader'] = certsubjectheader

    if clientcerthash:
        payload['sslaction']['clientcerthash'] = clientcerthash

    if certhashheader:
        payload['sslaction']['certhashheader'] = certhashheader

    if clientcertfingerprint:
        payload['sslaction']['clientcertfingerprint'] = clientcertfingerprint

    if certfingerprintheader:
        payload['sslaction']['certfingerprintheader'] = certfingerprintheader

    if certfingerprintdigest:
        payload['sslaction']['certfingerprintdigest'] = certfingerprintdigest

    if clientcertissuer:
        payload['sslaction']['clientcertissuer'] = clientcertissuer

    if certissuerheader:
        payload['sslaction']['certissuerheader'] = certissuerheader

    if sessionid:
        payload['sslaction']['sessionid'] = sessionid

    if sessionidheader:
        payload['sslaction']['sessionidheader'] = sessionidheader

    if cipher:
        payload['sslaction']['cipher'] = cipher

    if cipherheader:
        payload['sslaction']['cipherheader'] = cipherheader

    if clientcertnotbefore:
        payload['sslaction']['clientcertnotbefore'] = clientcertnotbefore

    if certnotbeforeheader:
        payload['sslaction']['certnotbeforeheader'] = certnotbeforeheader

    if clientcertnotafter:
        payload['sslaction']['clientcertnotafter'] = clientcertnotafter

    if certnotafterheader:
        payload['sslaction']['certnotafterheader'] = certnotafterheader

    if owasupport:
        payload['sslaction']['owasupport'] = owasupport

    execution = __proxy__['citrixns.post']('config/sslaction', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslcertkey(certkey=None, cert=None, key=None, password=None, fipskey=None, hsmkey=None, inform=None,
                   passplain=None, expirymonitor=None, notificationperiod=None, bundle=None, linkcertkeyname=None,
                   nodomaincheck=None, save=False):
    '''
    Add a new sslcertkey to the running configuration.

    certkey(str): Name for the certificate and private-key pair. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the certificate-key pair is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my cert" or my cert). Minimum length = 1

    cert(str): Name of and, optionally, path to the X509 certificate file that is used to form the certificate-key pair. The
        certificate file should be present on the appliances hard-disk drive or solid-state drive. Storing a certificate
        in any location other than the default might cause inconsistency in a high availability setup. /nsconfig/ssl/ is
        the default path. Minimum length = 1

    key(str): Name of and, optionally, path to the private-key file that is used to form the certificate-key pair. The
        certificate file should be present on the appliances hard-disk drive or solid-state drive. Storing a certificate
        in any location other than the default might cause inconsistency in a high availability setup. /nsconfig/ssl/ is
        the default path. Minimum length = 1

    password(bool): Passphrase that was used to encrypt the private-key. Use this option to load encrypted private-keys in
        PEM format.

    fipskey(str): Name of the FIPS key that was created inside the Hardware Security Module (HSM) of a FIPS appliance, or a
        key that was imported into the HSM. Minimum length = 1

    hsmkey(str): Name of the HSM key that was created in the External Hardware Security Module (HSM) of a FIPS appliance.
        Minimum length = 1

    inform(str): Input format of the certificate and the private-key files. The three formats supported by the appliance are:
        PEM - Privacy Enhanced Mail DER - Distinguished Encoding Rule PFX - Personal Information Exchange. Default value:
        PEM Possible values = DER, PEM, PFX

    passplain(str): Pass phrase used to encrypt the private-key. Required when adding an encrypted private-key in PEM format.
        Minimum length = 1

    expirymonitor(str): Issue an alert when the certificate is about to expire. Possible values = ENABLED, DISABLED

    notificationperiod(int): Time, in number of days, before certificate expiration, at which to generate an alert that the
        certificate is about to expire. Minimum value = 10 Maximum value = 100

    bundle(str): Parse the certificate chain as a single file after linking the server certificate to its issuers certificate
        within the file. Default value: NO Possible values = YES, NO

    linkcertkeyname(str): Name of the Certificate Authority certificate-key pair to which to link a certificate-key pair.
        Minimum length = 1

    nodomaincheck(bool): Override the check for matching domain names during a certificate update operation.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslcertkey <args>

    '''

    result = {}

    payload = {'sslcertkey': {}}

    if certkey:
        payload['sslcertkey']['certkey'] = certkey

    if cert:
        payload['sslcertkey']['cert'] = cert

    if key:
        payload['sslcertkey']['key'] = key

    if password:
        payload['sslcertkey']['password'] = password

    if fipskey:
        payload['sslcertkey']['fipskey'] = fipskey

    if hsmkey:
        payload['sslcertkey']['hsmkey'] = hsmkey

    if inform:
        payload['sslcertkey']['inform'] = inform

    if passplain:
        payload['sslcertkey']['passplain'] = passplain

    if expirymonitor:
        payload['sslcertkey']['expirymonitor'] = expirymonitor

    if notificationperiod:
        payload['sslcertkey']['notificationperiod'] = notificationperiod

    if bundle:
        payload['sslcertkey']['bundle'] = bundle

    if linkcertkeyname:
        payload['sslcertkey']['linkcertkeyname'] = linkcertkeyname

    if nodomaincheck:
        payload['sslcertkey']['nodomaincheck'] = nodomaincheck

    execution = __proxy__['citrixns.post']('config/sslcertkey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslcertkey_sslocspresponder_binding(priority=None, ca=None, certkey=None, ocspresponder=None, save=False):
    '''
    Add a new sslcertkey_sslocspresponder_binding to the running configuration.

    priority(int): ocsp priority.

    ca(bool): The certificate-key pair being unbound is a Certificate Authority (CA) certificate. If you choose this option,
        the certificate-key pair is unbound from the list of CA certificates that were bound to the specified SSL virtual
        server or SSL service.

    certkey(str): Name of the certificate-key pair. Minimum length = 1

    ocspresponder(str): OCSP responders bound to this certkey.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslcertkey_sslocspresponder_binding <args>

    '''

    result = {}

    payload = {'sslcertkey_sslocspresponder_binding': {}}

    if priority:
        payload['sslcertkey_sslocspresponder_binding']['priority'] = priority

    if ca:
        payload['sslcertkey_sslocspresponder_binding']['ca'] = ca

    if certkey:
        payload['sslcertkey_sslocspresponder_binding']['certkey'] = certkey

    if ocspresponder:
        payload['sslcertkey_sslocspresponder_binding']['ocspresponder'] = ocspresponder

    execution = __proxy__['citrixns.post']('config/sslcertkey_sslocspresponder_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslcipher(ciphergroupname=None, ciphgrpalias=None, ciphername=None, cipherpriority=None, sslprofile=None,
                  save=False):
    '''
    Add a new sslcipher to the running configuration.

    ciphergroupname(str): Name for the user-defined cipher group. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the cipher group is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my ciphergroup" or my ciphergroup). Minimum length = 1

    ciphgrpalias(str): The individual cipher name(s), a user-defined cipher group, or a system predefined cipher alias that
        will be added to the predefined cipher alias that will be added to the group cipherGroupName. If a cipher alias
        or a cipher group is specified, all the individual ciphers in the cipher alias or group will be added to the
        user-defined cipher group. Minimum length = 1

    ciphername(str): Cipher name.

    cipherpriority(int): This indicates priority assigned to the particular cipher. Minimum value = 1

    sslprofile(str): Name of the profile to which cipher is attached.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslcipher <args>

    '''

    result = {}

    payload = {'sslcipher': {}}

    if ciphergroupname:
        payload['sslcipher']['ciphergroupname'] = ciphergroupname

    if ciphgrpalias:
        payload['sslcipher']['ciphgrpalias'] = ciphgrpalias

    if ciphername:
        payload['sslcipher']['ciphername'] = ciphername

    if cipherpriority:
        payload['sslcipher']['cipherpriority'] = cipherpriority

    if sslprofile:
        payload['sslcipher']['sslprofile'] = sslprofile

    execution = __proxy__['citrixns.post']('config/sslcipher', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslcipher_sslciphersuite_binding(ciphername=None, ciphgrpals=None, cipherpriority=None, description=None,
                                         ciphergroupname=None, save=False):
    '''
    Add a new sslcipher_sslciphersuite_binding to the running configuration.

    ciphername(str): Cipher name.

    ciphgrpals(str): A cipher-suite can consist of an individual cipher name, the system predefined cipher-alias name, or
        user defined cipher-group name. Minimum length = 1

    cipherpriority(int): This indicates priority assigned to the particular cipher. Minimum value = 1

    description(str): Cipher suite description.

    ciphergroupname(str): Name for the user-defined cipher group. Must begin with an ASCII alphanumeric or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslcipher_sslciphersuite_binding <args>

    '''

    result = {}

    payload = {'sslcipher_sslciphersuite_binding': {}}

    if ciphername:
        payload['sslcipher_sslciphersuite_binding']['ciphername'] = ciphername

    if ciphgrpals:
        payload['sslcipher_sslciphersuite_binding']['ciphgrpals'] = ciphgrpals

    if cipherpriority:
        payload['sslcipher_sslciphersuite_binding']['cipherpriority'] = cipherpriority

    if description:
        payload['sslcipher_sslciphersuite_binding']['description'] = description

    if ciphergroupname:
        payload['sslcipher_sslciphersuite_binding']['ciphergroupname'] = ciphergroupname

    execution = __proxy__['citrixns.post']('config/sslcipher_sslciphersuite_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslcrl(crlname=None, crlpath=None, inform=None, refresh=None, cacert=None, method=None, server=None, url=None,
               port=None, basedn=None, scope=None, interval=None, day=None, time=None, binddn=None, password=None,
               binary=None, cacertfile=None, cakeyfile=None, indexfile=None, revoke=None, gencrl=None, save=False):
    '''
    Add a new sslcrl to the running configuration.

    crlname(str): Name for the Certificate Revocation List (CRL). Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the CRL is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my crl" or my crl). Minimum length = 1

    crlpath(str): Path to the CRL file. /var/netscaler/ssl/ is the default path. Minimum length = 1

    inform(str): Input format of the CRL file. The two formats supported on the appliance are: PEM - Privacy Enhanced Mail.
        DER - Distinguished Encoding Rule. Default value: PEM Possible values = DER, PEM

    refresh(str): Set CRL auto refresh. Possible values = ENABLED, DISABLED

    cacert(str): CA certificate that has issued the CRL. Required if CRL Auto Refresh is selected. Install the CA certificate
        on the appliance before adding the CRL. Minimum length = 1

    method(str): Method for CRL refresh. If LDAP is selected, specify the method, CA certificate, base DN, port, and LDAP
        server name. If HTTP is selected, specify the CA certificate, method, URL, and port. Cannot be changed after a
        CRL is added. Possible values = HTTP, LDAP

    server(str): IP address of the LDAP server from which to fetch the CRLs. Minimum length = 1

    url(str): URL of the CRL distribution point.

    port(int): Port for the LDAP server. Minimum value = 1

    basedn(str): Base distinguished name (DN), which is used in an LDAP search to search for a CRL. Citrix recommends
        searching for the Base DN instead of the Issuer Name from the CA certificate, because the Issuer Name field might
        not exactly match the LDAP directory structures DN. Minimum length = 1

    scope(str): Extent of the search operation on the LDAP server. Available settings function as follows: One - One level
        below Base DN. Base - Exactly the same level as Base DN. Default value: One Possible values = Base, One

    interval(str): CRL refresh interval. Use the NONE setting to unset this parameter. Possible values = MONTHLY, WEEKLY,
        DAILY, NONE

    day(int): Day on which to refresh the CRL, or, if the Interval parameter is not set, the number of days after which to
        refresh the CRL. If Interval is set to MONTHLY, specify the date. If Interval is set to WEEKLY, specify the day
        of the week (for example, Sun=0 and Sat=6). This parameter is not applicable if the Interval is set to DAILY.
        Minimum value = 0 Maximum value = 31

    time(str): Time, in hours (1-24) and minutes (1-60), at which to refresh the CRL.

    binddn(str): Bind distinguished name (DN) to be used to access the CRL object in the LDAP repository if access to the
        LDAP repository is restricted or anonymous access is not allowed. Minimum length = 1

    password(str): Password to access the CRL in the LDAP repository if access to the LDAP repository is restricted or
        anonymous access is not allowed. Minimum length = 1

    binary(str): Set the LDAP-based CRL retrieval mode to binary. Default value: NO Possible values = YES, NO

    cacertfile(str): Name of and, optionally, path to the CA certificate file. /nsconfig/ssl/ is the default path. Maximum
        length = 63

    cakeyfile(str): Name of and, optionally, path to the CA key file. /nsconfig/ssl/ is the default path. Maximum length =
        63

    indexfile(str): Name of and, optionally, path to the file containing the serial numbers of all the certificates that are
        revoked. Revoked certificates are appended to the file. /nsconfig/ssl/ is the default path. Maximum length = 63

    revoke(str): Name of and, optionally, path to the certificate to be revoked. /nsconfig/ssl/ is the default path. Maximum
        length = 63

    gencrl(str): Name of and, optionally, path to the CRL file to be generated. The list of certificates that have been
        revoked is obtained from the index file. /nsconfig/ssl/ is the default path. Maximum length = 63

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslcrl <args>

    '''

    result = {}

    payload = {'sslcrl': {}}

    if crlname:
        payload['sslcrl']['crlname'] = crlname

    if crlpath:
        payload['sslcrl']['crlpath'] = crlpath

    if inform:
        payload['sslcrl']['inform'] = inform

    if refresh:
        payload['sslcrl']['refresh'] = refresh

    if cacert:
        payload['sslcrl']['cacert'] = cacert

    if method:
        payload['sslcrl']['method'] = method

    if server:
        payload['sslcrl']['server'] = server

    if url:
        payload['sslcrl']['url'] = url

    if port:
        payload['sslcrl']['port'] = port

    if basedn:
        payload['sslcrl']['basedn'] = basedn

    if scope:
        payload['sslcrl']['scope'] = scope

    if interval:
        payload['sslcrl']['interval'] = interval

    if day:
        payload['sslcrl']['day'] = day

    if time:
        payload['sslcrl']['time'] = time

    if binddn:
        payload['sslcrl']['binddn'] = binddn

    if password:
        payload['sslcrl']['password'] = password

    if binary:
        payload['sslcrl']['binary'] = binary

    if cacertfile:
        payload['sslcrl']['cacertfile'] = cacertfile

    if cakeyfile:
        payload['sslcrl']['cakeyfile'] = cakeyfile

    if indexfile:
        payload['sslcrl']['indexfile'] = indexfile

    if revoke:
        payload['sslcrl']['revoke'] = revoke

    if gencrl:
        payload['sslcrl']['gencrl'] = gencrl

    execution = __proxy__['citrixns.post']('config/sslcrl', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_ssldtlsprofile(name=None, pmtudiscovery=None, maxrecordsize=None, maxretrytime=None, helloverifyrequest=None,
                       terminatesession=None, maxpacketsize=None, save=False):
    '''
    Add a new ssldtlsprofile to the running configuration.

    name(str): Name for the DTLS profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),equals sign (=), and hyphen
        (-) characters. Cannot be changed after the profile is created. Minimum length = 1 Maximum length = 127

    pmtudiscovery(str): Source for the maximum record size value. If ENABLED, the value is taken from the PMTU table. If
        DISABLED, the value is taken from the profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    maxrecordsize(int): Maximum size of records that can be sent if PMTU is disabled. Default value: 1459 Minimum value = 250
        Maximum value = 1459

    maxretrytime(int): Wait for the specified time, in seconds, before resending the request. Default value: 3

    helloverifyrequest(str): Send a Hello Verify request to validate the client. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    terminatesession(str): Terminate the session if the message authentication code (MAC) of the client and server do not
        match. Default value: DISABLED Possible values = ENABLED, DISABLED

    maxpacketsize(int): Maximum number of packets to reassemble. This value helps protect against a fragmented packet attack.
        Default value: 120 Minimum value = 0 Maximum value = 86400

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_ssldtlsprofile <args>

    '''

    result = {}

    payload = {'ssldtlsprofile': {}}

    if name:
        payload['ssldtlsprofile']['name'] = name

    if pmtudiscovery:
        payload['ssldtlsprofile']['pmtudiscovery'] = pmtudiscovery

    if maxrecordsize:
        payload['ssldtlsprofile']['maxrecordsize'] = maxrecordsize

    if maxretrytime:
        payload['ssldtlsprofile']['maxretrytime'] = maxretrytime

    if helloverifyrequest:
        payload['ssldtlsprofile']['helloverifyrequest'] = helloverifyrequest

    if terminatesession:
        payload['ssldtlsprofile']['terminatesession'] = terminatesession

    if maxpacketsize:
        payload['ssldtlsprofile']['maxpacketsize'] = maxpacketsize

    execution = __proxy__['citrixns.post']('config/ssldtlsprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslglobal_sslpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                    gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None, save=False):
    '''
    Add a new sslglobal_sslpolicy_binding to the running configuration.

    priority(int): The priority of the policy binding.

    globalbindtype(str): . Default value: SYSTEM_GLOBAL Possible values = SYSTEM_GLOBAL, VPN_GLOBAL, RNAT_GLOBAL

    policyname(str): The name for the SSL policy.

    labelname(str): Name of the virtual server or user-defined policy label to invoke if the policy evaluates to TRUE.

    gotopriorityexpression(str): Expression or other value specifying the next policy to be evaluated if the current policy
        evaluates to TRUE. Specify one of the following values: * NEXT - Evaluate the policy with the next higher
        priority number. * END - End policy evaluation. * USE_INVOCATION_RESULT - Applicable if this policy invokes
        another policy label. If the final goto in the invoked policy label has a value of END, the evaluation stops. If
        the final goto is anything other than END, the current policy label performs a NEXT. * A default syntax
        expression that evaluates to a number. If you specify an expression, the number to which it evaluates determines
        the next policy to evaluate, as follows: * If the expression evaluates to a higher numbered priority, the policy
        with that priority is evaluated next. * If the expression evaluates to the priority of the current policy, the
        policy with the next higher numbered priority is evaluated next. * If the expression evaluates to a number that
        is larger than the largest numbered priority, policy evaluation ends. An UNDEF event is triggered if: * The
        expression is invalid. * The expression evaluates to a priority number that is numerically lower than the current
        policys priority. * The expression evaluates to a priority number that is between the current policys priority
        number (say, 30) and the highest priority number (say, 100), but does not match any configured priority number
        (for example, the expression evaluates to the number 85). This example assumes that the priority number
        increments by 10 for every successive policy, and therefore a priority number of 85 does not exist in the policy
        label. Default value: "END"

    invoke(bool): Invoke policies bound to a virtual server, service, or policy label. After the invoked policies are
        evaluated, the flow returns to the policy with the next priority.

    ns_type(str): Global bind point to which the policy is bound. Possible values = CONTROL_OVERRIDE, CONTROL_DEFAULT,
        DATA_OVERRIDE, DATA_DEFAULT

    labeltype(str): Type of policy label to invoke. Specify virtual server for a policy label associated with a virtual
        server, or policy label for a user-defined policy label. Possible values = vserver, service, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslglobal_sslpolicy_binding <args>

    '''

    result = {}

    payload = {'sslglobal_sslpolicy_binding': {}}

    if priority:
        payload['sslglobal_sslpolicy_binding']['priority'] = priority

    if globalbindtype:
        payload['sslglobal_sslpolicy_binding']['globalbindtype'] = globalbindtype

    if policyname:
        payload['sslglobal_sslpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['sslglobal_sslpolicy_binding']['labelname'] = labelname

    if gotopriorityexpression:
        payload['sslglobal_sslpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['sslglobal_sslpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['sslglobal_sslpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['sslglobal_sslpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/sslglobal_sslpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslhsmkey(hsmkeyname=None, hsmtype=None, key=None, serialnum=None, password=None, save=False):
    '''
    Add a new sslhsmkey to the running configuration.

    hsmkeyname(str): . Minimum length = 1

    hsmtype(str): Type of HSM. Default value: THALES Possible values = THALES, SAFENET

    key(str): Name of and, optionally, path to the HSM key file. /var/opt/nfast/kmdata/local/ is the default path. Applies
        only to THALES HSM. Maximum length = 63

    serialnum(str): Serial number of the partition on which the key is present. Applies only to SafeNet HSM. Maximum length =
        16

    password(str): Password for a partition. Applies only to SafeNet HSM. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslhsmkey <args>

    '''

    result = {}

    payload = {'sslhsmkey': {}}

    if hsmkeyname:
        payload['sslhsmkey']['hsmkeyname'] = hsmkeyname

    if hsmtype:
        payload['sslhsmkey']['hsmtype'] = hsmtype

    if key:
        payload['sslhsmkey']['key'] = key

    if serialnum:
        payload['sslhsmkey']['serialnum'] = serialnum

    if password:
        payload['sslhsmkey']['password'] = password

    execution = __proxy__['citrixns.post']('config/sslhsmkey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslocspresponder(name=None, url=None, cache=None, cachetimeout=None, batchingdepth=None, batchingdelay=None,
                         resptimeout=None, respondercert=None, trustresponder=None, producedattimeskew=None,
                         signingcert=None, usenonce=None, insertclientcert=None, save=False):
    '''
    Add a new sslocspresponder to the running configuration.

    name(str): Name for the OCSP responder. Cannot begin with a hash (#) or space character and must contain only ASCII
        alphanumeric, underscore (_), hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the responder is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my responder" or my responder). Minimum length = 1

    url(str): URL of the OCSP responder. Minimum length = 1

    cache(str): Enable caching of responses. Caching of responses received from the OCSP responder enables faster responses
        to the clients and reduces the load on the OCSP responder. Possible values = ENABLED, DISABLED

    cachetimeout(int): Timeout for caching the OCSP response. After the timeout, the NetScaler sends a fresh request to the
        OCSP responder for the certificate status. If a timeout is not specified, the timeout provided in the OCSP
        response applies. Default value: 1 Minimum value = 1 Maximum value = 1440

    batchingdepth(int): Number of client certificates to batch together into one OCSP request. Batching avoids overloading
        the OCSP responder. A value of 1 signifies that each request is queried independently. For a value greater than
        1, specify a timeout (batching delay) to avoid inordinately delaying the processing of a single certificate.
        Minimum value = 1 Maximum value = 8

    batchingdelay(int): Maximum time, in milliseconds, to wait to accumulate OCSP requests to batch. Does not apply if the
        Batching Depth is 1. Minimum value = 0 Maximum value = 10000

    resptimeout(int): Time, in milliseconds, to wait for an OCSP response. When this time elapses, an error message appears
        or the transaction is forwarded, depending on the settings on the virtual server. Includes Batching Delay time.
        Minimum value = 0 Maximum value = 120000

    respondercert(str): . Minimum length = 1

    trustresponder(bool): A certificate to use to validate OCSP responses. Alternatively, if -trustResponder is specified, no
        verification will be done on the reponse. If both are omitted, only the response times (producedAt, lastUpdate,
        nextUpdate) will be verified.

    producedattimeskew(int): Time, in seconds, for which the NetScaler waits before considering the response as invalid. The
        response is considered invalid if the Produced At time stamp in the OCSP response exceeds or precedes the current
        NetScaler clock time by the amount of time specified. Default value: 300 Minimum value = 0 Maximum value = 86400

    signingcert(str): Certificate-key pair that is used to sign OCSP requests. If this parameter is not set, the requests are
        not signed. Minimum length = 1

    usenonce(str): Enable the OCSP nonce extension, which is designed to prevent replay attacks. Possible values = YES, NO

    insertclientcert(str): Include the complete client certificate in the OCSP request. Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslocspresponder <args>

    '''

    result = {}

    payload = {'sslocspresponder': {}}

    if name:
        payload['sslocspresponder']['name'] = name

    if url:
        payload['sslocspresponder']['url'] = url

    if cache:
        payload['sslocspresponder']['cache'] = cache

    if cachetimeout:
        payload['sslocspresponder']['cachetimeout'] = cachetimeout

    if batchingdepth:
        payload['sslocspresponder']['batchingdepth'] = batchingdepth

    if batchingdelay:
        payload['sslocspresponder']['batchingdelay'] = batchingdelay

    if resptimeout:
        payload['sslocspresponder']['resptimeout'] = resptimeout

    if respondercert:
        payload['sslocspresponder']['respondercert'] = respondercert

    if trustresponder:
        payload['sslocspresponder']['trustresponder'] = trustresponder

    if producedattimeskew:
        payload['sslocspresponder']['producedattimeskew'] = producedattimeskew

    if signingcert:
        payload['sslocspresponder']['signingcert'] = signingcert

    if usenonce:
        payload['sslocspresponder']['usenonce'] = usenonce

    if insertclientcert:
        payload['sslocspresponder']['insertclientcert'] = insertclientcert

    execution = __proxy__['citrixns.post']('config/sslocspresponder', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslpolicy(name=None, rule=None, reqaction=None, action=None, undefaction=None, comment=None, save=False):
    '''
    Add a new sslpolicy to the running configuration.

    name(str): Name for the new SSL policy. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Written in the classic or default syntax. Note: Maximum length
        of a string literal in the expression is 255 characters. A longer string can be split into smaller strings of up
        to 255 characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" (Classic
        expressions are not supported in the cluster build.)  The following requirements apply only to the NetScaler CLI:
        * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. * If
        the expression itself includes double quotation marks, escape the quotations by using the character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    reqaction(str): The name of the action to be performed on the request. Refer to add ssl action command to add a new
        action. Builtin actions like NOOP, RESET, DROP, CLIENTAUTH and NOCLIENTAUTH are also allowed. Minimum length = 1

    action(str): Name of the built-in or user-defined action to perform on the request. Available built-in actions are NOOP,
        RESET, DROP, CLIENTAUTH and NOCLIENTAUTH.

    undefaction(str): Name of the action to be performed when the result of rule evaluation is undefined. Possible values for
        control policies: CLIENTAUTH, NOCLIENTAUTH, NOOP, RESET, DROP. Possible values for data policies: NOOP, RESET,
        DROP.

    comment(str): Any comments associated with this policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslpolicy <args>

    '''

    result = {}

    payload = {'sslpolicy': {}}

    if name:
        payload['sslpolicy']['name'] = name

    if rule:
        payload['sslpolicy']['rule'] = rule

    if reqaction:
        payload['sslpolicy']['reqaction'] = reqaction

    if action:
        payload['sslpolicy']['action'] = action

    if undefaction:
        payload['sslpolicy']['undefaction'] = undefaction

    if comment:
        payload['sslpolicy']['comment'] = comment

    execution = __proxy__['citrixns.post']('config/sslpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslpolicylabel(labelname=None, ns_type=None, save=False):
    '''
    Add a new sslpolicylabel to the running configuration.

    labelname(str): Name for the SSL policy label. Must begin with an ASCII alphanumeric or underscore (_) character, and
        must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy label is created.  The following requirement applies
        only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my label" or my label).

    ns_type(str): Type of policies that the policy label can contain. Possible values = CONTROL, DATA

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslpolicylabel <args>

    '''

    result = {}

    payload = {'sslpolicylabel': {}}

    if labelname:
        payload['sslpolicylabel']['labelname'] = labelname

    if ns_type:
        payload['sslpolicylabel']['type'] = ns_type

    execution = __proxy__['citrixns.post']('config/sslpolicylabel', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslpolicylabel_sslpolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, labeltype=None,
                                         labelname=None, invoke_labelname=None, invoke=None, save=False):
    '''
    Add a new sslpolicylabel_sslpolicy_binding to the running configuration.

    priority(int): Specifies the priority of the policy.

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    policyname(str): Name of the SSL policy to bind to the policy label.

    labeltype(str): Type of policy label invocation. Possible values = vserver, service, policylabel

    labelname(str): Name of the SSL policy label to which to bind policies.

    invoke_labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE.

    invoke(bool): Invoke policies bound to a policy label. After the invoked policies are evaluated, the flow returns to the
        policy with the next priority.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslpolicylabel_sslpolicy_binding <args>

    '''

    result = {}

    payload = {'sslpolicylabel_sslpolicy_binding': {}}

    if priority:
        payload['sslpolicylabel_sslpolicy_binding']['priority'] = priority

    if gotopriorityexpression:
        payload['sslpolicylabel_sslpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if policyname:
        payload['sslpolicylabel_sslpolicy_binding']['policyname'] = policyname

    if labeltype:
        payload['sslpolicylabel_sslpolicy_binding']['labeltype'] = labeltype

    if labelname:
        payload['sslpolicylabel_sslpolicy_binding']['labelname'] = labelname

    if invoke_labelname:
        payload['sslpolicylabel_sslpolicy_binding']['invoke_labelname'] = invoke_labelname

    if invoke:
        payload['sslpolicylabel_sslpolicy_binding']['invoke'] = invoke

    execution = __proxy__['citrixns.post']('config/sslpolicylabel_sslpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslprofile(name=None, sslprofiletype=None, dhcount=None, dh=None, dhfile=None, ersa=None, ersacount=None,
                   sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None, clientauth=None,
                   clientcert=None, dhkeyexpsizelimit=None, sslredirect=None, redirectportrewrite=None, ssl3=None,
                   tls1=None, tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None,
                   commonname=None, pushenctrigger=None, sendclosenotify=None, cleartextport=None,
                   insertionencoding=None, denysslreneg=None, quantumsize=None, strictcachecks=None,
                   encrypttriggerpktcount=None, pushflag=None, dropreqwithnohostheader=None, pushenctriggertimeout=None,
                   ssltriggertimeout=None, clientauthuseboundcachain=None, sessionticket=None,
                   sessionticketlifetime=None, hsts=None, maxage=None, includesubdomains=None, ciphername=None,
                   cipherpriority=None, strictsigdigestcheck=None, save=False):
    '''
    Add a new sslprofile to the running configuration.

    name(str): Name for the SSL profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the profile is created. Minimum length = 1 Maximum length = 127

    sslprofiletype(str): Type of profile. Front end profiles apply to the entity that receives requests from a client.
        Backend profiles apply to the entity that sends client requests to a server. Default value: FrontEnd Possible
        values = BackEnd, FrontEnd

    dhcount(int): Number of interactions, between the client and the NetScaler appliance, after which the DH private-public
        pair is regenerated. A value of zero (0) specifies infinite use (no refresh). This parameter is not applicable
        when configuring a backend profile. Minimum value = 0 Maximum value = 65534

    dh(str): State of Diffie-Hellman (DH) key exchange. This parameter is not applicable when configuring a backend profile.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    dhfile(str): The file name and path for the DH parameter. Minimum length = 1

    ersa(str): State of Ephemeral RSA (eRSA) key exchange. Ephemeral RSA allows clients that support only export ciphers to
        communicate with the secure server even if the server certificate does not support export clients. The ephemeral
        RSA key is automatically generated when you bind an export cipher to an SSL or TCP-based SSL virtual server or
        service. When you remove the export cipher, the eRSA key is not deleted. It is reused at a later date when
        another export cipher is bound to an SSL or TCP-based SSL virtual server or service. The eRSA key is deleted when
        the appliance restarts. This parameter is not applicable when configuring a backend profile. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    ersacount(int): The refresh count for the re-generation of RSA public-key and private-key pair. Minimum value = 0 Maximum
        value = 65534

    sessreuse(str): State of session reuse. Establishing the initial handshake requires CPU-intensive public key encryption
        operations. With the ENABLED setting, session key exchange is avoided for session resumption requests received
        from the client. Default value: ENABLED Possible values = ENABLED, DISABLED

    sesstimeout(int): The Session timeout value in seconds. Minimum value = 0 Maximum value = 4294967294

    cipherredirect(str): State of Cipher Redirect. If this parameter is set to ENABLED, you can configure an SSL virtual
        server or service to display meaningful error messages if the SSL handshake fails because of a cipher mismatch
        between the virtual server or service and the client. This parameter is not applicable when configuring a backend
        profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    cipherurl(str): The redirect URL to be used with the Cipher Redirect feature.

    clientauth(str): State of client authentication. In service-based SSL offload, the service terminates the SSL handshake
        if the SSL client does not provide a valid certificate.  This parameter is not applicable when configuring a
        backend profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    clientcert(str): The rule for client certificate requirement in client authentication. Possible values = Mandatory,
        Optional

    dhkeyexpsizelimit(str): This option enables the use of NIST recommended (NIST Special Publication 800-56A) bit size for
        private-key size. For example, for DH params of size 2048bit, the private-key size recommended is 224bits. This
        is rounded-up to 256bits. Default value: DISABLED Possible values = ENABLED, DISABLED

    sslredirect(str): State of HTTPS redirects for the SSL service.  For an SSL session, if the client browser receives a
        redirect message, the browser tries to connect to the new location. However, the secure SSL session breaks if the
        object has moved from a secure site (https://) to an unsecure site (http://). Typically, a warning message
        appears on the screen, prompting the user to continue or disconnect. If SSL Redirect is ENABLED, the redirect
        message is automatically converted from http:// to https:// and the SSL session does not break. This parameter is
        not applicable when configuring a backend profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    redirectportrewrite(str): State of the port rewrite while performing HTTPS redirect. If this parameter is set to ENABLED,
        and the URL from the server does not contain the standard port, the port is rewritten to the standard. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    ssl3(str): State of SSLv3 protocol support for the SSL profile. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    tls1(str): State of TLSv1.0 protocol support for the SSL profile. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls11(str): State of TLSv1.1 protocol support for the SSL profile. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls12(str): State of TLSv1.2 protocol support for the SSL profile. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    snienable(str): State of the Server Name Indication (SNI) feature on the virtual server and service-based offload. SNI
        helps to enable SSL encryption on multiple domains on a single virtual server or service if the domains are
        controlled by the same organization and share the same second-level domain name. For example, *.sports.net can be
        used to secure domains such as login.sports.net and help.sports.net. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    ocspstapling(str): State of OCSP stapling support on the SSL virtual server. Supported only if the protocol used is
        higher than SSLv3. Possible values: ENABLED: The appliance sends a request to the OCSP responder to check the
        status of the server certificate and caches the response for the specified time. If the response is valid at the
        time of SSL handshake with the client, the OCSP-based server certificate status is sent to the client during the
        handshake. DISABLED: The appliance does not check the status of the server certificate. . Default value: DISABLED
        Possible values = ENABLED, DISABLED

    serverauth(str): State of server authentication support for the SSL Backend profile. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    commonname(str): Name to be checked against the CommonName (CN) field in the server certificate bound to the SSL server.
        Minimum length = 1

    pushenctrigger(str): Trigger encryption on the basis of the PUSH flag value. Available settings function as follows: *
        ALWAYS - Any PUSH packet triggers encryption. * IGNORE - Ignore PUSH packet for triggering encryption. * MERGE -
        For a consecutive sequence of PUSH packets, the last PUSH packet triggers encryption. * TIMER - PUSH packet
        triggering encryption is delayed by the time defined in the set ssl parameter command or in the Change Advanced
        SSL Settings dialog box. Possible values = Always, Merge, Ignore, Timer

    sendclosenotify(str): Enable sending SSL Close-Notify at the end of a transaction. Default value: YES Possible values =
        YES, NO

    cleartextport(int): Port on which clear-text data is sent by the appliance to the server. Do not specify this parameter
        for SSL offloading with end-to-end encryption. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    insertionencoding(str): Encoding method used to insert the subject or issuers name in HTTP requests to servers. Default
        value: Unicode Possible values = Unicode, UTF-8

    denysslreneg(str): Deny renegotiation in specified circumstances. Available settings function as follows: * NO - Allow
        SSL renegotiation. * FRONTEND_CLIENT - Deny secure and nonsecure SSL renegotiation initiated by the client. *
        FRONTEND_CLIENTSERVER - Deny secure and nonsecure SSL renegotiation initiated by the client or the NetScaler
        during policy-based client authentication.  * ALL - Deny all secure and nonsecure SSL renegotiation. * NONSECURE
        - Deny nonsecure SSL renegotiation. Allows only clients that support RFC 5746. Default value: ALL Possible values
        = NO, FRONTEND_CLIENT, FRONTEND_CLIENTSERVER, ALL, NONSECURE

    quantumsize(str): Amount of data to collect before the data is pushed to the crypto hardware for encryption. For large
        downloads, a larger quantum size better utilizes the crypto resources. Default value: 8192 Possible values =
        4096, 8192, 16384

    strictcachecks(str): Enable strict CA certificate checks on the appliance. Default value: NO Possible values = YES, NO

    encrypttriggerpktcount(int): Maximum number of queued packets after which encryption is triggered. Use this setting for
        SSL transactions that send small packets from server to NetScaler. Default value: 45 Minimum value = 10 Maximum
        value = 50

    pushflag(int): Insert PUSH flag into decrypted, encrypted, or all records. If the PUSH flag is set to a value other than
        0, the buffered records are forwarded on the basis of the value of the PUSH flag. Available settings function as
        follows: 0 - Auto (PUSH flag is not set.) 1 - Insert PUSH flag into every decrypted record. 2 -Insert PUSH flag
        into every encrypted record. 3 - Insert PUSH flag into every decrypted and encrypted record. Minimum value = 0
        Maximum value = 3

    dropreqwithnohostheader(str): Host header check for SNI enabled sessions. If this check is enabled and the HTTP request
        does not contain the host header for SNI enabled sessions, the request is dropped. Default value: NO Possible
        values = YES, NO

    pushenctriggertimeout(int): PUSH encryption trigger timeout value. The timeout value is applied only if you set the Push
        Encryption Trigger parameter to Timer in the SSL virtual server settings. Default value: 1 Minimum value = 1
        Maximum value = 200

    ssltriggertimeout(int): Time, in milliseconds, after which encryption is triggered for transactions that are not tracked
        on the NetScaler appliance because their length is not known. There can be a delay of up to 10ms from the
        specified timeout value before the packet is pushed into the queue. Default value: 100 Minimum value = 1 Maximum
        value = 200

    clientauthuseboundcachain(str): Certficates bound on the VIP are used for validating the client cert. Certficates came
        along with client cert are not used for validating the client cert. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    sessionticket(str): This option enables the use of session tickets, as per the RFC 5077. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    sessionticketlifetime(int): This option sets the life time of session tickets issued by NS in secs. Default value: 300
        Minimum value = 0 Maximum value = 172800

    hsts(str): State of TLSv1.0 protocol support for the SSL Virtual Server. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    maxage(int): Set max-age value for STS header. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    includesubdomains(str): Set include sub domain value for STS header. Default value: NO Possible values = YES, NO

    ciphername(str): The cipher group/alias/individual cipher configuration.

    cipherpriority(int): cipher priority. Minimum value = 1

    strictsigdigestcheck(str): Parameter indicating to check whether peer entity certificate during TLS1.2 handshake is
        signed with one of signature-hash combination supported by Netscaler. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslprofile <args>

    '''

    result = {}

    payload = {'sslprofile': {}}

    if name:
        payload['sslprofile']['name'] = name

    if sslprofiletype:
        payload['sslprofile']['sslprofiletype'] = sslprofiletype

    if dhcount:
        payload['sslprofile']['dhcount'] = dhcount

    if dh:
        payload['sslprofile']['dh'] = dh

    if dhfile:
        payload['sslprofile']['dhfile'] = dhfile

    if ersa:
        payload['sslprofile']['ersa'] = ersa

    if ersacount:
        payload['sslprofile']['ersacount'] = ersacount

    if sessreuse:
        payload['sslprofile']['sessreuse'] = sessreuse

    if sesstimeout:
        payload['sslprofile']['sesstimeout'] = sesstimeout

    if cipherredirect:
        payload['sslprofile']['cipherredirect'] = cipherredirect

    if cipherurl:
        payload['sslprofile']['cipherurl'] = cipherurl

    if clientauth:
        payload['sslprofile']['clientauth'] = clientauth

    if clientcert:
        payload['sslprofile']['clientcert'] = clientcert

    if dhkeyexpsizelimit:
        payload['sslprofile']['dhkeyexpsizelimit'] = dhkeyexpsizelimit

    if sslredirect:
        payload['sslprofile']['sslredirect'] = sslredirect

    if redirectportrewrite:
        payload['sslprofile']['redirectportrewrite'] = redirectportrewrite

    if ssl3:
        payload['sslprofile']['ssl3'] = ssl3

    if tls1:
        payload['sslprofile']['tls1'] = tls1

    if tls11:
        payload['sslprofile']['tls11'] = tls11

    if tls12:
        payload['sslprofile']['tls12'] = tls12

    if snienable:
        payload['sslprofile']['snienable'] = snienable

    if ocspstapling:
        payload['sslprofile']['ocspstapling'] = ocspstapling

    if serverauth:
        payload['sslprofile']['serverauth'] = serverauth

    if commonname:
        payload['sslprofile']['commonname'] = commonname

    if pushenctrigger:
        payload['sslprofile']['pushenctrigger'] = pushenctrigger

    if sendclosenotify:
        payload['sslprofile']['sendclosenotify'] = sendclosenotify

    if cleartextport:
        payload['sslprofile']['cleartextport'] = cleartextport

    if insertionencoding:
        payload['sslprofile']['insertionencoding'] = insertionencoding

    if denysslreneg:
        payload['sslprofile']['denysslreneg'] = denysslreneg

    if quantumsize:
        payload['sslprofile']['quantumsize'] = quantumsize

    if strictcachecks:
        payload['sslprofile']['strictcachecks'] = strictcachecks

    if encrypttriggerpktcount:
        payload['sslprofile']['encrypttriggerpktcount'] = encrypttriggerpktcount

    if pushflag:
        payload['sslprofile']['pushflag'] = pushflag

    if dropreqwithnohostheader:
        payload['sslprofile']['dropreqwithnohostheader'] = dropreqwithnohostheader

    if pushenctriggertimeout:
        payload['sslprofile']['pushenctriggertimeout'] = pushenctriggertimeout

    if ssltriggertimeout:
        payload['sslprofile']['ssltriggertimeout'] = ssltriggertimeout

    if clientauthuseboundcachain:
        payload['sslprofile']['clientauthuseboundcachain'] = clientauthuseboundcachain

    if sessionticket:
        payload['sslprofile']['sessionticket'] = sessionticket

    if sessionticketlifetime:
        payload['sslprofile']['sessionticketlifetime'] = sessionticketlifetime

    if hsts:
        payload['sslprofile']['hsts'] = hsts

    if maxage:
        payload['sslprofile']['maxage'] = maxage

    if includesubdomains:
        payload['sslprofile']['includesubdomains'] = includesubdomains

    if ciphername:
        payload['sslprofile']['ciphername'] = ciphername

    if cipherpriority:
        payload['sslprofile']['cipherpriority'] = cipherpriority

    if strictsigdigestcheck:
        payload['sslprofile']['strictsigdigestcheck'] = strictsigdigestcheck

    execution = __proxy__['citrixns.post']('config/sslprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslprofile_ecccurve_binding(cipherpriority=None, name=None, ecccurvename=None, save=False):
    '''
    Add a new sslprofile_ecccurve_binding to the running configuration.

    cipherpriority(int): Priority of the cipher binding. Minimum value = 1 Maximum value = 1000

    name(str): Name of the SSL profile. Minimum length = 1 Maximum length = 127

    ecccurvename(str): Named ECC curve bound to vserver/service. Possible values = ALL, P_224, P_256, P_384, P_521

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslprofile_ecccurve_binding <args>

    '''

    result = {}

    payload = {'sslprofile_ecccurve_binding': {}}

    if cipherpriority:
        payload['sslprofile_ecccurve_binding']['cipherpriority'] = cipherpriority

    if name:
        payload['sslprofile_ecccurve_binding']['name'] = name

    if ecccurvename:
        payload['sslprofile_ecccurve_binding']['ecccurvename'] = ecccurvename

    execution = __proxy__['citrixns.post']('config/sslprofile_ecccurve_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslprofile_sslcipher_binding(ciphername=None, cipheraliasname=None, cipherpriority=None, name=None,
                                     description=None, save=False):
    '''
    Add a new sslprofile_sslcipher_binding to the running configuration.

    ciphername(str): Name of the cipher. Minimum length = 1

    cipheraliasname(str): The name of the cipher group/alias/individual cipheri bindings.

    cipherpriority(int): cipher priority. Minimum value = 1

    name(str): Name of the SSL profile. Minimum length = 1 Maximum length = 127

    description(str): The cipher suite description.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslprofile_sslcipher_binding <args>

    '''

    result = {}

    payload = {'sslprofile_sslcipher_binding': {}}

    if ciphername:
        payload['sslprofile_sslcipher_binding']['ciphername'] = ciphername

    if cipheraliasname:
        payload['sslprofile_sslcipher_binding']['cipheraliasname'] = cipheraliasname

    if cipherpriority:
        payload['sslprofile_sslcipher_binding']['cipherpriority'] = cipherpriority

    if name:
        payload['sslprofile_sslcipher_binding']['name'] = name

    if description:
        payload['sslprofile_sslcipher_binding']['description'] = description

    execution = __proxy__['citrixns.post']('config/sslprofile_sslcipher_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslprofile_sslciphersuite_binding(ciphername=None, cipherpriority=None, name=None, description=None,
                                          save=False):
    '''
    Add a new sslprofile_sslciphersuite_binding to the running configuration.

    ciphername(str): The cipher group/alias/individual cipher configuration.

    cipherpriority(int): cipher priority. Minimum value = 1

    name(str): Name of the SSL profile. Minimum length = 1 Maximum length = 127

    description(str): The cipher suite description.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslprofile_sslciphersuite_binding <args>

    '''

    result = {}

    payload = {'sslprofile_sslciphersuite_binding': {}}

    if ciphername:
        payload['sslprofile_sslciphersuite_binding']['ciphername'] = ciphername

    if cipherpriority:
        payload['sslprofile_sslciphersuite_binding']['cipherpriority'] = cipherpriority

    if name:
        payload['sslprofile_sslciphersuite_binding']['name'] = name

    if description:
        payload['sslprofile_sslciphersuite_binding']['description'] = description

    execution = __proxy__['citrixns.post']('config/sslprofile_sslciphersuite_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservice_ecccurve_binding(ecccurvename=None, servicename=None, save=False):
    '''
    Add a new sslservice_ecccurve_binding to the running configuration.

    ecccurvename(str): Named ECC curve bound to service/vserver. Possible values = ALL, P_224, P_256, P_384, P_521

    servicename(str): Name of the SSL service for which to set advanced configuration. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservice_ecccurve_binding <args>

    '''

    result = {}

    payload = {'sslservice_ecccurve_binding': {}}

    if ecccurvename:
        payload['sslservice_ecccurve_binding']['ecccurvename'] = ecccurvename

    if servicename:
        payload['sslservice_ecccurve_binding']['servicename'] = servicename

    execution = __proxy__['citrixns.post']('config/sslservice_ecccurve_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservice_sslcertkey_binding(ca=None, crlcheck=None, servicename=None, certkeyname=None, skipcaname=None,
                                      snicert=None, ocspcheck=None, save=False):
    '''
    Add a new sslservice_sslcertkey_binding to the running configuration.

    ca(bool): CA certificate.

    crlcheck(str): The state of the CRL check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    servicename(str): Name of the SSL service for which to set advanced configuration. Minimum length = 1

    certkeyname(str): The certificate key pair binding.

    skipcaname(bool): The flag is used to indicate whether this particular CA certificates CA_Name needs to be sent to the
        SSL client while requesting for client certificate in a SSL handshake.

    snicert(bool): The name of the CertKey. Use this option to bind Certkey(s) which will be used in SNI processing.

    ocspcheck(str): Rule to use for the OCSP responder associated with the CA certificate during client authentication. If
        MANDATORY is specified, deny all SSL clients if the OCSP check fails because of connectivity issues with the
        remote OCSP server, or any other reason that prevents the OCSP check. With the OPTIONAL setting, allow SSL
        clients even if the OCSP check fails except when the client certificate is revoked. Possible values = Mandatory,
        Optional

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservice_sslcertkey_binding <args>

    '''

    result = {}

    payload = {'sslservice_sslcertkey_binding': {}}

    if ca:
        payload['sslservice_sslcertkey_binding']['ca'] = ca

    if crlcheck:
        payload['sslservice_sslcertkey_binding']['crlcheck'] = crlcheck

    if servicename:
        payload['sslservice_sslcertkey_binding']['servicename'] = servicename

    if certkeyname:
        payload['sslservice_sslcertkey_binding']['certkeyname'] = certkeyname

    if skipcaname:
        payload['sslservice_sslcertkey_binding']['skipcaname'] = skipcaname

    if snicert:
        payload['sslservice_sslcertkey_binding']['snicert'] = snicert

    if ocspcheck:
        payload['sslservice_sslcertkey_binding']['ocspcheck'] = ocspcheck

    execution = __proxy__['citrixns.post']('config/sslservice_sslcertkey_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservice_sslcipher_binding(ciphername=None, cipheraliasname=None, servicename=None, description=None,
                                     save=False):
    '''
    Add a new sslservice_sslcipher_binding to the running configuration.

    ciphername(str): Name of the individual cipher, user-defined cipher group, or predefined (built-in) cipher alias.

    cipheraliasname(str): The cipher group/alias/individual cipher configuration.

    servicename(str): Name of the SSL service for which to set advanced configuration. Minimum length = 1

    description(str): The cipher suite description.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservice_sslcipher_binding <args>

    '''

    result = {}

    payload = {'sslservice_sslcipher_binding': {}}

    if ciphername:
        payload['sslservice_sslcipher_binding']['ciphername'] = ciphername

    if cipheraliasname:
        payload['sslservice_sslcipher_binding']['cipheraliasname'] = cipheraliasname

    if servicename:
        payload['sslservice_sslcipher_binding']['servicename'] = servicename

    if description:
        payload['sslservice_sslcipher_binding']['description'] = description

    execution = __proxy__['citrixns.post']('config/sslservice_sslcipher_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservice_sslciphersuite_binding(ciphername=None, servicename=None, description=None, save=False):
    '''
    Add a new sslservice_sslciphersuite_binding to the running configuration.

    ciphername(str): The cipher group/alias/individual cipher configuration.

    servicename(str): Name of the SSL service for which to set advanced configuration. Minimum length = 1

    description(str): The cipher suite description.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservice_sslciphersuite_binding <args>

    '''

    result = {}

    payload = {'sslservice_sslciphersuite_binding': {}}

    if ciphername:
        payload['sslservice_sslciphersuite_binding']['ciphername'] = ciphername

    if servicename:
        payload['sslservice_sslciphersuite_binding']['servicename'] = servicename

    if description:
        payload['sslservice_sslciphersuite_binding']['description'] = description

    execution = __proxy__['citrixns.post']('config/sslservice_sslciphersuite_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservice_sslpolicy_binding(priority=None, policyname=None, labelname=None, servicename=None,
                                     gotopriorityexpression=None, invoke=None, labeltype=None, save=False):
    '''
    Add a new sslservice_sslpolicy_binding to the running configuration.

    priority(int): The priority of the policies bound to this SSL service. Minimum value = 0 Maximum value = 65534

    policyname(str): The SSL policy binding.

    labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE.

    servicename(str): Name of the SSL service for which to set advanced configuration. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag. This attribute is relevant only for ADVANCED policies.

    labeltype(str): Type of policy label invocation. Possible values = vserver, service, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservice_sslpolicy_binding <args>

    '''

    result = {}

    payload = {'sslservice_sslpolicy_binding': {}}

    if priority:
        payload['sslservice_sslpolicy_binding']['priority'] = priority

    if policyname:
        payload['sslservice_sslpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['sslservice_sslpolicy_binding']['labelname'] = labelname

    if servicename:
        payload['sslservice_sslpolicy_binding']['servicename'] = servicename

    if gotopriorityexpression:
        payload['sslservice_sslpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['sslservice_sslpolicy_binding']['invoke'] = invoke

    if labeltype:
        payload['sslservice_sslpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/sslservice_sslpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservicegroup_ecccurve_binding(servicegroupname=None, ecccurvename=None, save=False):
    '''
    Add a new sslservicegroup_ecccurve_binding to the running configuration.

    servicegroupname(str): The name of the SSL service to which the SSL policy needs to be bound. Minimum length = 1

    ecccurvename(str): Named ECC curve bound to servicegroup. Possible values = ALL, P_224, P_256, P_384, P_521

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservicegroup_ecccurve_binding <args>

    '''

    result = {}

    payload = {'sslservicegroup_ecccurve_binding': {}}

    if servicegroupname:
        payload['sslservicegroup_ecccurve_binding']['servicegroupname'] = servicegroupname

    if ecccurvename:
        payload['sslservicegroup_ecccurve_binding']['ecccurvename'] = ecccurvename

    execution = __proxy__['citrixns.post']('config/sslservicegroup_ecccurve_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservicegroup_sslcertkey_binding(servicegroupname=None, ca=None, crlcheck=None, certkeyname=None, snicert=None,
                                           ocspcheck=None, save=False):
    '''
    Add a new sslservicegroup_sslcertkey_binding to the running configuration.

    servicegroupname(str): The name of the SSL service to which the SSL policy needs to be bound. Minimum length = 1

    ca(bool): CA certificate.

    crlcheck(str): The state of the CRL check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    certkeyname(str): The name of the certificate bound to the SSL service group.

    snicert(bool): The name of the CertKey. Use this option to bind Certkey(s) which will be used in SNI processing.

    ocspcheck(str): The state of the OCSP check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservicegroup_sslcertkey_binding <args>

    '''

    result = {}

    payload = {'sslservicegroup_sslcertkey_binding': {}}

    if servicegroupname:
        payload['sslservicegroup_sslcertkey_binding']['servicegroupname'] = servicegroupname

    if ca:
        payload['sslservicegroup_sslcertkey_binding']['ca'] = ca

    if crlcheck:
        payload['sslservicegroup_sslcertkey_binding']['crlcheck'] = crlcheck

    if certkeyname:
        payload['sslservicegroup_sslcertkey_binding']['certkeyname'] = certkeyname

    if snicert:
        payload['sslservicegroup_sslcertkey_binding']['snicert'] = snicert

    if ocspcheck:
        payload['sslservicegroup_sslcertkey_binding']['ocspcheck'] = ocspcheck

    execution = __proxy__['citrixns.post']('config/sslservicegroup_sslcertkey_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservicegroup_sslcipher_binding(ciphername=None, cipheraliasname=None, servicegroupname=None, description=None,
                                          save=False):
    '''
    Add a new sslservicegroup_sslcipher_binding to the running configuration.

    ciphername(str): A cipher-suite can consist of an individual cipher name, the system predefined cipher-alias name, or
        user defined cipher-group name.

    cipheraliasname(str): The name of the cipher group/alias/name configured for the SSL service group.

    servicegroupname(str): The name of the SSL service to which the SSL policy needs to be bound. Minimum length = 1

    description(str): The description of the cipher.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservicegroup_sslcipher_binding <args>

    '''

    result = {}

    payload = {'sslservicegroup_sslcipher_binding': {}}

    if ciphername:
        payload['sslservicegroup_sslcipher_binding']['ciphername'] = ciphername

    if cipheraliasname:
        payload['sslservicegroup_sslcipher_binding']['cipheraliasname'] = cipheraliasname

    if servicegroupname:
        payload['sslservicegroup_sslcipher_binding']['servicegroupname'] = servicegroupname

    if description:
        payload['sslservicegroup_sslcipher_binding']['description'] = description

    execution = __proxy__['citrixns.post']('config/sslservicegroup_sslcipher_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslservicegroup_sslciphersuite_binding(ciphername=None, servicegroupname=None, description=None, save=False):
    '''
    Add a new sslservicegroup_sslciphersuite_binding to the running configuration.

    ciphername(str): The name of the cipher group/alias/name configured for the SSL service group.

    servicegroupname(str): The name of the SSL service to which the SSL policy needs to be bound. Minimum length = 1

    description(str): The description of the cipher.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslservicegroup_sslciphersuite_binding <args>

    '''

    result = {}

    payload = {'sslservicegroup_sslciphersuite_binding': {}}

    if ciphername:
        payload['sslservicegroup_sslciphersuite_binding']['ciphername'] = ciphername

    if servicegroupname:
        payload['sslservicegroup_sslciphersuite_binding']['servicegroupname'] = servicegroupname

    if description:
        payload['sslservicegroup_sslciphersuite_binding']['description'] = description

    execution = __proxy__['citrixns.post']('config/sslservicegroup_sslciphersuite_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslvserver_ecccurve_binding(ecccurvename=None, vservername=None, save=False):
    '''
    Add a new sslvserver_ecccurve_binding to the running configuration.

    ecccurvename(str): Named ECC curve bound to vserver/service. Possible values = ALL, P_224, P_256, P_384, P_521

    vservername(str): Name of the SSL virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslvserver_ecccurve_binding <args>

    '''

    result = {}

    payload = {'sslvserver_ecccurve_binding': {}}

    if ecccurvename:
        payload['sslvserver_ecccurve_binding']['ecccurvename'] = ecccurvename

    if vservername:
        payload['sslvserver_ecccurve_binding']['vservername'] = vservername

    execution = __proxy__['citrixns.post']('config/sslvserver_ecccurve_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslvserver_sslcertkey_binding(ca=None, crlcheck=None, vservername=None, certkeyname=None, skipcaname=None,
                                      snicert=None, ocspcheck=None, save=False):
    '''
    Add a new sslvserver_sslcertkey_binding to the running configuration.

    ca(bool): CA certificate.

    crlcheck(str): The state of the CRL check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    vservername(str): Name of the SSL virtual server. Minimum length = 1

    certkeyname(str): The name of the certificate key pair binding.

    skipcaname(bool): The flag is used to indicate whether this particular CA certificates CA_Name needs to be sent to the
        SSL client while requesting for client certificate in a SSL handshake.

    snicert(bool): The name of the CertKey. Use this option to bind Certkey(s) which will be used in SNI processing.

    ocspcheck(str): The state of the OCSP check parameter. (Mandatory/Optional). Possible values = Mandatory, Optional

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslvserver_sslcertkey_binding <args>

    '''

    result = {}

    payload = {'sslvserver_sslcertkey_binding': {}}

    if ca:
        payload['sslvserver_sslcertkey_binding']['ca'] = ca

    if crlcheck:
        payload['sslvserver_sslcertkey_binding']['crlcheck'] = crlcheck

    if vservername:
        payload['sslvserver_sslcertkey_binding']['vservername'] = vservername

    if certkeyname:
        payload['sslvserver_sslcertkey_binding']['certkeyname'] = certkeyname

    if skipcaname:
        payload['sslvserver_sslcertkey_binding']['skipcaname'] = skipcaname

    if snicert:
        payload['sslvserver_sslcertkey_binding']['snicert'] = snicert

    if ocspcheck:
        payload['sslvserver_sslcertkey_binding']['ocspcheck'] = ocspcheck

    execution = __proxy__['citrixns.post']('config/sslvserver_sslcertkey_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslvserver_sslcipher_binding(ciphername=None, cipheraliasname=None, description=None, vservername=None,
                                     save=False):
    '''
    Add a new sslvserver_sslcipher_binding to the running configuration.

    ciphername(str): Name of the individual cipher, user-defined cipher group, or predefined (built-in) cipher alias.

    cipheraliasname(str): The name of the cipher group/alias/individual cipheri bindings.

    description(str): The cipher suite description.

    vservername(str): Name of the SSL virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslvserver_sslcipher_binding <args>

    '''

    result = {}

    payload = {'sslvserver_sslcipher_binding': {}}

    if ciphername:
        payload['sslvserver_sslcipher_binding']['ciphername'] = ciphername

    if cipheraliasname:
        payload['sslvserver_sslcipher_binding']['cipheraliasname'] = cipheraliasname

    if description:
        payload['sslvserver_sslcipher_binding']['description'] = description

    if vservername:
        payload['sslvserver_sslcipher_binding']['vservername'] = vservername

    execution = __proxy__['citrixns.post']('config/sslvserver_sslcipher_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslvserver_sslciphersuite_binding(ciphername=None, description=None, vservername=None, save=False):
    '''
    Add a new sslvserver_sslciphersuite_binding to the running configuration.

    ciphername(str): The cipher group/alias/individual cipher configuration.

    description(str): The cipher suite description.

    vservername(str): Name of the SSL virtual server. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslvserver_sslciphersuite_binding <args>

    '''

    result = {}

    payload = {'sslvserver_sslciphersuite_binding': {}}

    if ciphername:
        payload['sslvserver_sslciphersuite_binding']['ciphername'] = ciphername

    if description:
        payload['sslvserver_sslciphersuite_binding']['description'] = description

    if vservername:
        payload['sslvserver_sslciphersuite_binding']['vservername'] = vservername

    execution = __proxy__['citrixns.post']('config/sslvserver_sslciphersuite_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_sslvserver_sslpolicy_binding(priority=None, policyname=None, labelname=None, vservername=None,
                                     gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None,
                                     save=False):
    '''
    Add a new sslvserver_sslpolicy_binding to the running configuration.

    priority(int): The priority of the policies bound to this SSL service. Minimum value = 0 Maximum value = 65534

    policyname(str): The name of the SSL policy binding.

    labelname(str): Name of the label to invoke if the current policy rule evaluates to TRUE.

    vservername(str): Name of the SSL virtual server. Minimum length = 1

    gotopriorityexpression(str): Expression specifying the priority of the next policy which will get evaluated if the
        current policy rule evaluates to TRUE.

    invoke(bool): Invoke flag. This attribute is relevant only for ADVANCED policies.

    ns_type(str): Bind point to which to bind the policy. Possible Values: HANDSHAKE_REQ, HANDSHAKE_RES, CLIENTHELLO_REQ,
        CLIENTCERT_REQ, SERVERHELLO_RES, SERVERCERT_RES, SERVERHELLO_DONE_RES and REQUEST. These bindpoints mean: 1.
        HANDSHAKE_REQ: Policy evaluation will be done at the end of handshake on request side (request side means between
        client and NetScaler) 2. HANDSHAKE_RES: Policy evaluation will be done at the end of hadnshake on response side
        (response side means between Netscaler and server) 3. INTERCEPT_REQ: Policy evaluation will be done after
        receiving Client Hello on request side. 4. CLIENTCERT_REQ: Policy evaluation will be done after receiving Client
        Certificate on request side. 5. SERVERHELLO_RES: Policy evaluation will be done after receiving Server Hello on
        response side. 6. SERVERCERT_RES: Policy evaluation will be done after receiving Server Certificate on response
        side. 7. SERVERHELLO_DONE_RES: Policy evaluation will be done after receiving Server Hello Done on response side.
        8. REQUEST: Policy evaluation will be done at appplication above SSL. This bindpoint is default and is used for
        actions based on clientauth and client cert. Default value: REQUEST Possible values = HANDSHAKE_REQ,
        HANDSHAKE_RES, INTERCEPT_REQ, CLIENTCERT_REQ, SERVERHELLO_RES, SERVERCERT_RES, SERVERHELLO_DONE_RES, REQUEST

    labeltype(str): Type of policy label invocation. Possible values = vserver, service, policylabel

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.add_sslvserver_sslpolicy_binding <args>

    '''

    result = {}

    payload = {'sslvserver_sslpolicy_binding': {}}

    if priority:
        payload['sslvserver_sslpolicy_binding']['priority'] = priority

    if policyname:
        payload['sslvserver_sslpolicy_binding']['policyname'] = policyname

    if labelname:
        payload['sslvserver_sslpolicy_binding']['labelname'] = labelname

    if vservername:
        payload['sslvserver_sslpolicy_binding']['vservername'] = vservername

    if gotopriorityexpression:
        payload['sslvserver_sslpolicy_binding']['gotopriorityexpression'] = gotopriorityexpression

    if invoke:
        payload['sslvserver_sslpolicy_binding']['invoke'] = invoke

    if ns_type:
        payload['sslvserver_sslpolicy_binding']['type'] = ns_type

    if labeltype:
        payload['sslvserver_sslpolicy_binding']['labeltype'] = labeltype

    execution = __proxy__['citrixns.post']('config/sslvserver_sslpolicy_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_sslfipssimsource(targetsecret=None, save=False):
    '''
    Enables a sslfipssimsource matching the specified filter.

    targetsecret(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.enable_sslfipssimsource targetsecret=foo

    '''

    result = {}

    payload = {'sslfipssimsource': {}}

    if targetsecret:
        payload['sslfipssimsource']['targetsecret'] = targetsecret
    else:
        result['result'] = 'False'
        result['error'] = 'targetsecret value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/sslfipssimsource?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def enable_sslfipssimtarget(keyvector=None, save=False):
    '''
    Enables a sslfipssimtarget matching the specified filter.

    keyvector(str): Matches the enable command to the specified value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.enable_sslfipssimtarget keyvector=foo

    '''

    result = {}

    payload = {'sslfipssimtarget': {}}

    if keyvector:
        payload['sslfipssimtarget']['keyvector'] = keyvector
    else:
        result['result'] = 'False'
        result['error'] = 'keyvector value not specified.'
        return result

    execution = __proxy__['citrixns.post']('config/sslfipssimtarget?action=enable', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_sslaction(name=None, clientauth=None, clientcert=None, certheader=None, clientcertserialnumber=None,
                  certserialheader=None, clientcertsubject=None, certsubjectheader=None, clientcerthash=None,
                  certhashheader=None, clientcertfingerprint=None, certfingerprintheader=None,
                  certfingerprintdigest=None, clientcertissuer=None, certissuerheader=None, sessionid=None,
                  sessionidheader=None, cipher=None, cipherheader=None, clientcertnotbefore=None,
                  certnotbeforeheader=None, clientcertnotafter=None, certnotafterheader=None, owasupport=None):
    '''
    Show the running configuration for the sslaction config key.

    name(str): Filters results that only match the name field.

    clientauth(str): Filters results that only match the clientauth field.

    clientcert(str): Filters results that only match the clientcert field.

    certheader(str): Filters results that only match the certheader field.

    clientcertserialnumber(str): Filters results that only match the clientcertserialnumber field.

    certserialheader(str): Filters results that only match the certserialheader field.

    clientcertsubject(str): Filters results that only match the clientcertsubject field.

    certsubjectheader(str): Filters results that only match the certsubjectheader field.

    clientcerthash(str): Filters results that only match the clientcerthash field.

    certhashheader(str): Filters results that only match the certhashheader field.

    clientcertfingerprint(str): Filters results that only match the clientcertfingerprint field.

    certfingerprintheader(str): Filters results that only match the certfingerprintheader field.

    certfingerprintdigest(str): Filters results that only match the certfingerprintdigest field.

    clientcertissuer(str): Filters results that only match the clientcertissuer field.

    certissuerheader(str): Filters results that only match the certissuerheader field.

    sessionid(str): Filters results that only match the sessionid field.

    sessionidheader(str): Filters results that only match the sessionidheader field.

    cipher(str): Filters results that only match the cipher field.

    cipherheader(str): Filters results that only match the cipherheader field.

    clientcertnotbefore(str): Filters results that only match the clientcertnotbefore field.

    certnotbeforeheader(str): Filters results that only match the certnotbeforeheader field.

    clientcertnotafter(str): Filters results that only match the clientcertnotafter field.

    certnotafterheader(str): Filters results that only match the certnotafterheader field.

    owasupport(str): Filters results that only match the owasupport field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslaction

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if clientauth:
        search_filter.append(['clientauth', clientauth])

    if clientcert:
        search_filter.append(['clientcert', clientcert])

    if certheader:
        search_filter.append(['certheader', certheader])

    if clientcertserialnumber:
        search_filter.append(['clientcertserialnumber', clientcertserialnumber])

    if certserialheader:
        search_filter.append(['certserialheader', certserialheader])

    if clientcertsubject:
        search_filter.append(['clientcertsubject', clientcertsubject])

    if certsubjectheader:
        search_filter.append(['certsubjectheader', certsubjectheader])

    if clientcerthash:
        search_filter.append(['clientcerthash', clientcerthash])

    if certhashheader:
        search_filter.append(['certhashheader', certhashheader])

    if clientcertfingerprint:
        search_filter.append(['clientcertfingerprint', clientcertfingerprint])

    if certfingerprintheader:
        search_filter.append(['certfingerprintheader', certfingerprintheader])

    if certfingerprintdigest:
        search_filter.append(['certfingerprintdigest', certfingerprintdigest])

    if clientcertissuer:
        search_filter.append(['clientcertissuer', clientcertissuer])

    if certissuerheader:
        search_filter.append(['certissuerheader', certissuerheader])

    if sessionid:
        search_filter.append(['sessionid', sessionid])

    if sessionidheader:
        search_filter.append(['sessionidheader', sessionidheader])

    if cipher:
        search_filter.append(['cipher', cipher])

    if cipherheader:
        search_filter.append(['cipherheader', cipherheader])

    if clientcertnotbefore:
        search_filter.append(['clientcertnotbefore', clientcertnotbefore])

    if certnotbeforeheader:
        search_filter.append(['certnotbeforeheader', certnotbeforeheader])

    if clientcertnotafter:
        search_filter.append(['clientcertnotafter', clientcertnotafter])

    if certnotafterheader:
        search_filter.append(['certnotafterheader', certnotafterheader])

    if owasupport:
        search_filter.append(['owasupport', owasupport])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslaction{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslaction')

    return response


def get_sslcertbundle(name=None, src=None):
    '''
    Show the running configuration for the sslcertbundle config key.

    name(str): Filters results that only match the name field.

    src(str): Filters results that only match the src field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertbundle

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if src:
        search_filter.append(['src', src])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertbundle{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertbundle')

    return response


def get_sslcertchain(certkeyname=None):
    '''
    Show the running configuration for the sslcertchain config key.

    certkeyname(str): Filters results that only match the certkeyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertchain

    '''

    search_filter = []

    if certkeyname:
        search_filter.append(['certkeyname', certkeyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertchain{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertchain')

    return response


def get_sslcertchain_binding():
    '''
    Show the running configuration for the sslcertchain_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertchain_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertchain_binding'), 'sslcertchain_binding')

    return response


def get_sslcertchain_sslcertkey_binding(linkcertkeyname=None, certkeyname=None):
    '''
    Show the running configuration for the sslcertchain_sslcertkey_binding config key.

    linkcertkeyname(str): Filters results that only match the linkcertkeyname field.

    certkeyname(str): Filters results that only match the certkeyname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertchain_sslcertkey_binding

    '''

    search_filter = []

    if linkcertkeyname:
        search_filter.append(['linkcertkeyname', linkcertkeyname])

    if certkeyname:
        search_filter.append(['certkeyname', certkeyname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertchain_sslcertkey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertchain_sslcertkey_binding')

    return response


def get_sslcertfile(name=None, src=None):
    '''
    Show the running configuration for the sslcertfile config key.

    name(str): Filters results that only match the name field.

    src(str): Filters results that only match the src field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertfile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if src:
        search_filter.append(['src', src])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertfile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertfile')

    return response


def get_sslcertkey(certkey=None, cert=None, key=None, password=None, fipskey=None, hsmkey=None, inform=None,
                   passplain=None, expirymonitor=None, notificationperiod=None, bundle=None, linkcertkeyname=None,
                   nodomaincheck=None):
    '''
    Show the running configuration for the sslcertkey config key.

    certkey(str): Filters results that only match the certkey field.

    cert(str): Filters results that only match the cert field.

    key(str): Filters results that only match the key field.

    password(bool): Filters results that only match the password field.

    fipskey(str): Filters results that only match the fipskey field.

    hsmkey(str): Filters results that only match the hsmkey field.

    inform(str): Filters results that only match the inform field.

    passplain(str): Filters results that only match the passplain field.

    expirymonitor(str): Filters results that only match the expirymonitor field.

    notificationperiod(int): Filters results that only match the notificationperiod field.

    bundle(str): Filters results that only match the bundle field.

    linkcertkeyname(str): Filters results that only match the linkcertkeyname field.

    nodomaincheck(bool): Filters results that only match the nodomaincheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey

    '''

    search_filter = []

    if certkey:
        search_filter.append(['certkey', certkey])

    if cert:
        search_filter.append(['cert', cert])

    if key:
        search_filter.append(['key', key])

    if password:
        search_filter.append(['password', password])

    if fipskey:
        search_filter.append(['fipskey', fipskey])

    if hsmkey:
        search_filter.append(['hsmkey', hsmkey])

    if inform:
        search_filter.append(['inform', inform])

    if passplain:
        search_filter.append(['passplain', passplain])

    if expirymonitor:
        search_filter.append(['expirymonitor', expirymonitor])

    if notificationperiod:
        search_filter.append(['notificationperiod', notificationperiod])

    if bundle:
        search_filter.append(['bundle', bundle])

    if linkcertkeyname:
        search_filter.append(['linkcertkeyname', linkcertkeyname])

    if nodomaincheck:
        search_filter.append(['nodomaincheck', nodomaincheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertkey')

    return response


def get_sslcertkey_binding():
    '''
    Show the running configuration for the sslcertkey_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey_binding'), 'sslcertkey_binding')

    return response


def get_sslcertkey_crldistribution_binding(ca=None, issuer=None, certkey=None):
    '''
    Show the running configuration for the sslcertkey_crldistribution_binding config key.

    ca(bool): Filters results that only match the ca field.

    issuer(str): Filters results that only match the issuer field.

    certkey(str): Filters results that only match the certkey field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey_crldistribution_binding

    '''

    search_filter = []

    if ca:
        search_filter.append(['ca', ca])

    if issuer:
        search_filter.append(['issuer', issuer])

    if certkey:
        search_filter.append(['certkey', certkey])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey_crldistribution_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertkey_crldistribution_binding')

    return response


def get_sslcertkey_service_binding(servicegroupname=None, ca=None, service=None, servicename=None, certkey=None):
    '''
    Show the running configuration for the sslcertkey_service_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    ca(bool): Filters results that only match the ca field.

    service(bool): Filters results that only match the service field.

    servicename(str): Filters results that only match the servicename field.

    certkey(str): Filters results that only match the certkey field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey_service_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if ca:
        search_filter.append(['ca', ca])

    if service:
        search_filter.append(['service', service])

    if servicename:
        search_filter.append(['servicename', servicename])

    if certkey:
        search_filter.append(['certkey', certkey])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey_service_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertkey_service_binding')

    return response


def get_sslcertkey_sslocspresponder_binding(priority=None, ca=None, certkey=None, ocspresponder=None):
    '''
    Show the running configuration for the sslcertkey_sslocspresponder_binding config key.

    priority(int): Filters results that only match the priority field.

    ca(bool): Filters results that only match the ca field.

    certkey(str): Filters results that only match the certkey field.

    ocspresponder(str): Filters results that only match the ocspresponder field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey_sslocspresponder_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if ca:
        search_filter.append(['ca', ca])

    if certkey:
        search_filter.append(['certkey', certkey])

    if ocspresponder:
        search_filter.append(['ocspresponder', ocspresponder])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey_sslocspresponder_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertkey_sslocspresponder_binding')

    return response


def get_sslcertkey_sslprofile_binding(ca=None, sslprofile=None, certkey=None):
    '''
    Show the running configuration for the sslcertkey_sslprofile_binding config key.

    ca(bool): Filters results that only match the ca field.

    sslprofile(str): Filters results that only match the sslprofile field.

    certkey(str): Filters results that only match the certkey field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey_sslprofile_binding

    '''

    search_filter = []

    if ca:
        search_filter.append(['ca', ca])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    if certkey:
        search_filter.append(['certkey', certkey])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey_sslprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertkey_sslprofile_binding')

    return response


def get_sslcertkey_sslvserver_binding(vserver=None, ca=None, vservername=None, servername=None, certkey=None):
    '''
    Show the running configuration for the sslcertkey_sslvserver_binding config key.

    vserver(bool): Filters results that only match the vserver field.

    ca(bool): Filters results that only match the ca field.

    vservername(str): Filters results that only match the vservername field.

    servername(str): Filters results that only match the servername field.

    certkey(str): Filters results that only match the certkey field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertkey_sslvserver_binding

    '''

    search_filter = []

    if vserver:
        search_filter.append(['vserver', vserver])

    if ca:
        search_filter.append(['ca', ca])

    if vservername:
        search_filter.append(['vservername', vservername])

    if servername:
        search_filter.append(['servername', servername])

    if certkey:
        search_filter.append(['certkey', certkey])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertkey_sslvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertkey_sslvserver_binding')

    return response


def get_sslcertlink():
    '''
    Show the running configuration for the sslcertlink config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcertlink

    '''

    search_filter = []

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcertlink{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcertlink')

    return response


def get_sslcipher(ciphergroupname=None, ciphgrpalias=None, ciphername=None, cipherpriority=None, sslprofile=None):
    '''
    Show the running configuration for the sslcipher config key.

    ciphergroupname(str): Filters results that only match the ciphergroupname field.

    ciphgrpalias(str): Filters results that only match the ciphgrpalias field.

    ciphername(str): Filters results that only match the ciphername field.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    sslprofile(str): Filters results that only match the sslprofile field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcipher

    '''

    search_filter = []

    if ciphergroupname:
        search_filter.append(['ciphergroupname', ciphergroupname])

    if ciphgrpalias:
        search_filter.append(['ciphgrpalias', ciphgrpalias])

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcipher{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcipher')

    return response


def get_sslcipher_binding():
    '''
    Show the running configuration for the sslcipher_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcipher_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcipher_binding'), 'sslcipher_binding')

    return response


def get_sslcipher_individualcipher_binding(ciphername=None, ciphgrpals=None, cipherpriority=None, description=None,
                                           ciphergroupname=None, cipheroperation=None):
    '''
    Show the running configuration for the sslcipher_individualcipher_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    ciphgrpals(str): Filters results that only match the ciphgrpals field.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    description(str): Filters results that only match the description field.

    ciphergroupname(str): Filters results that only match the ciphergroupname field.

    cipheroperation(str): Filters results that only match the cipheroperation field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcipher_individualcipher_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if ciphgrpals:
        search_filter.append(['ciphgrpals', ciphgrpals])

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if description:
        search_filter.append(['description', description])

    if ciphergroupname:
        search_filter.append(['ciphergroupname', ciphergroupname])

    if cipheroperation:
        search_filter.append(['cipheroperation', cipheroperation])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcipher_individualcipher_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcipher_individualcipher_binding')

    return response


def get_sslcipher_sslciphersuite_binding(ciphername=None, ciphgrpals=None, cipherpriority=None, description=None,
                                         ciphergroupname=None):
    '''
    Show the running configuration for the sslcipher_sslciphersuite_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    ciphgrpals(str): Filters results that only match the ciphgrpals field.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    description(str): Filters results that only match the description field.

    ciphergroupname(str): Filters results that only match the ciphergroupname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcipher_sslciphersuite_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if ciphgrpals:
        search_filter.append(['ciphgrpals', ciphgrpals])

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if description:
        search_filter.append(['description', description])

    if ciphergroupname:
        search_filter.append(['ciphergroupname', ciphergroupname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcipher_sslciphersuite_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcipher_sslciphersuite_binding')

    return response


def get_sslcipher_sslprofile_binding(cipherpriority=None, ciphgrpals=None, description=None, sslprofile=None,
                                     ciphergroupname=None, cipheroperation=None):
    '''
    Show the running configuration for the sslcipher_sslprofile_binding config key.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    ciphgrpals(str): Filters results that only match the ciphgrpals field.

    description(str): Filters results that only match the description field.

    sslprofile(str): Filters results that only match the sslprofile field.

    ciphergroupname(str): Filters results that only match the ciphergroupname field.

    cipheroperation(str): Filters results that only match the cipheroperation field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcipher_sslprofile_binding

    '''

    search_filter = []

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if ciphgrpals:
        search_filter.append(['ciphgrpals', ciphgrpals])

    if description:
        search_filter.append(['description', description])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    if ciphergroupname:
        search_filter.append(['ciphergroupname', ciphergroupname])

    if cipheroperation:
        search_filter.append(['cipheroperation', cipheroperation])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcipher_sslprofile_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcipher_sslprofile_binding')

    return response


def get_sslciphersuite(ciphername=None):
    '''
    Show the running configuration for the sslciphersuite config key.

    ciphername(str): Filters results that only match the ciphername field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslciphersuite

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslciphersuite{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslciphersuite')

    return response


def get_sslcrl(crlname=None, crlpath=None, inform=None, refresh=None, cacert=None, method=None, server=None, url=None,
               port=None, basedn=None, scope=None, interval=None, day=None, time=None, binddn=None, password=None,
               binary=None, cacertfile=None, cakeyfile=None, indexfile=None, revoke=None, gencrl=None):
    '''
    Show the running configuration for the sslcrl config key.

    crlname(str): Filters results that only match the crlname field.

    crlpath(str): Filters results that only match the crlpath field.

    inform(str): Filters results that only match the inform field.

    refresh(str): Filters results that only match the refresh field.

    cacert(str): Filters results that only match the cacert field.

    method(str): Filters results that only match the method field.

    server(str): Filters results that only match the server field.

    url(str): Filters results that only match the url field.

    port(int): Filters results that only match the port field.

    basedn(str): Filters results that only match the basedn field.

    scope(str): Filters results that only match the scope field.

    interval(str): Filters results that only match the interval field.

    day(int): Filters results that only match the day field.

    time(str): Filters results that only match the time field.

    binddn(str): Filters results that only match the binddn field.

    password(str): Filters results that only match the password field.

    binary(str): Filters results that only match the binary field.

    cacertfile(str): Filters results that only match the cacertfile field.

    cakeyfile(str): Filters results that only match the cakeyfile field.

    indexfile(str): Filters results that only match the indexfile field.

    revoke(str): Filters results that only match the revoke field.

    gencrl(str): Filters results that only match the gencrl field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcrl

    '''

    search_filter = []

    if crlname:
        search_filter.append(['crlname', crlname])

    if crlpath:
        search_filter.append(['crlpath', crlpath])

    if inform:
        search_filter.append(['inform', inform])

    if refresh:
        search_filter.append(['refresh', refresh])

    if cacert:
        search_filter.append(['cacert', cacert])

    if method:
        search_filter.append(['method', method])

    if server:
        search_filter.append(['server', server])

    if url:
        search_filter.append(['url', url])

    if port:
        search_filter.append(['port', port])

    if basedn:
        search_filter.append(['basedn', basedn])

    if scope:
        search_filter.append(['scope', scope])

    if interval:
        search_filter.append(['interval', interval])

    if day:
        search_filter.append(['day', day])

    if time:
        search_filter.append(['time', time])

    if binddn:
        search_filter.append(['binddn', binddn])

    if password:
        search_filter.append(['password', password])

    if binary:
        search_filter.append(['binary', binary])

    if cacertfile:
        search_filter.append(['cacertfile', cacertfile])

    if cakeyfile:
        search_filter.append(['cakeyfile', cakeyfile])

    if indexfile:
        search_filter.append(['indexfile', indexfile])

    if revoke:
        search_filter.append(['revoke', revoke])

    if gencrl:
        search_filter.append(['gencrl', gencrl])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcrl{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcrl')

    return response


def get_sslcrl_binding():
    '''
    Show the running configuration for the sslcrl_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcrl_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcrl_binding'), 'sslcrl_binding')

    return response


def get_sslcrl_serialnumber_binding(number=None, crlname=None):
    '''
    Show the running configuration for the sslcrl_serialnumber_binding config key.

    number(str): Filters results that only match the number field.

    crlname(str): Filters results that only match the crlname field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcrl_serialnumber_binding

    '''

    search_filter = []

    if number:
        search_filter.append(['number', number])

    if crlname:
        search_filter.append(['crlname', crlname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcrl_serialnumber_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcrl_serialnumber_binding')

    return response


def get_sslcrlfile(name=None, src=None):
    '''
    Show the running configuration for the sslcrlfile config key.

    name(str): Filters results that only match the name field.

    src(str): Filters results that only match the src field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslcrlfile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if src:
        search_filter.append(['src', src])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslcrlfile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslcrlfile')

    return response


def get_ssldhfile(name=None, src=None):
    '''
    Show the running configuration for the ssldhfile config key.

    name(str): Filters results that only match the name field.

    src(str): Filters results that only match the src field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_ssldhfile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if src:
        search_filter.append(['src', src])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ssldhfile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ssldhfile')

    return response


def get_ssldtlsprofile(name=None, pmtudiscovery=None, maxrecordsize=None, maxretrytime=None, helloverifyrequest=None,
                       terminatesession=None, maxpacketsize=None):
    '''
    Show the running configuration for the ssldtlsprofile config key.

    name(str): Filters results that only match the name field.

    pmtudiscovery(str): Filters results that only match the pmtudiscovery field.

    maxrecordsize(int): Filters results that only match the maxrecordsize field.

    maxretrytime(int): Filters results that only match the maxretrytime field.

    helloverifyrequest(str): Filters results that only match the helloverifyrequest field.

    terminatesession(str): Filters results that only match the terminatesession field.

    maxpacketsize(int): Filters results that only match the maxpacketsize field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_ssldtlsprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if pmtudiscovery:
        search_filter.append(['pmtudiscovery', pmtudiscovery])

    if maxrecordsize:
        search_filter.append(['maxrecordsize', maxrecordsize])

    if maxretrytime:
        search_filter.append(['maxretrytime', maxretrytime])

    if helloverifyrequest:
        search_filter.append(['helloverifyrequest', helloverifyrequest])

    if terminatesession:
        search_filter.append(['terminatesession', terminatesession])

    if maxpacketsize:
        search_filter.append(['maxpacketsize', maxpacketsize])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/ssldtlsprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'ssldtlsprofile')

    return response


def get_sslfips():
    '''
    Show the running configuration for the sslfips config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslfips

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslfips'), 'sslfips')

    return response


def get_sslfipskey(fipskeyname=None, modulus=None, exponent=None, key=None, inform=None, wrapkeyname=None, iv=None):
    '''
    Show the running configuration for the sslfipskey config key.

    fipskeyname(str): Filters results that only match the fipskeyname field.

    modulus(int): Filters results that only match the modulus field.

    exponent(str): Filters results that only match the exponent field.

    key(str): Filters results that only match the key field.

    inform(str): Filters results that only match the inform field.

    wrapkeyname(str): Filters results that only match the wrapkeyname field.

    iv(str): Filters results that only match the iv field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslfipskey

    '''

    search_filter = []

    if fipskeyname:
        search_filter.append(['fipskeyname', fipskeyname])

    if modulus:
        search_filter.append(['modulus', modulus])

    if exponent:
        search_filter.append(['exponent', exponent])

    if key:
        search_filter.append(['key', key])

    if inform:
        search_filter.append(['inform', inform])

    if wrapkeyname:
        search_filter.append(['wrapkeyname', wrapkeyname])

    if iv:
        search_filter.append(['iv', iv])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslfipskey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslfipskey')

    return response


def get_sslglobal_binding():
    '''
    Show the running configuration for the sslglobal_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslglobal_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslglobal_binding'), 'sslglobal_binding')

    return response


def get_sslglobal_sslpolicy_binding(priority=None, globalbindtype=None, policyname=None, labelname=None,
                                    gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the sslglobal_sslpolicy_binding config key.

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

    salt '*' ssl.get_sslglobal_sslpolicy_binding

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
            __proxy__['citrixns.get']('config/sslglobal_sslpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslglobal_sslpolicy_binding')

    return response


def get_sslhsmkey(hsmkeyname=None, hsmtype=None, key=None, serialnum=None, password=None):
    '''
    Show the running configuration for the sslhsmkey config key.

    hsmkeyname(str): Filters results that only match the hsmkeyname field.

    hsmtype(str): Filters results that only match the hsmtype field.

    key(str): Filters results that only match the key field.

    serialnum(str): Filters results that only match the serialnum field.

    password(str): Filters results that only match the password field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslhsmkey

    '''

    search_filter = []

    if hsmkeyname:
        search_filter.append(['hsmkeyname', hsmkeyname])

    if hsmtype:
        search_filter.append(['hsmtype', hsmtype])

    if key:
        search_filter.append(['key', key])

    if serialnum:
        search_filter.append(['serialnum', serialnum])

    if password:
        search_filter.append(['password', password])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslhsmkey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslhsmkey')

    return response


def get_sslkeyfile(name=None, src=None, password=None):
    '''
    Show the running configuration for the sslkeyfile config key.

    name(str): Filters results that only match the name field.

    src(str): Filters results that only match the src field.

    password(str): Filters results that only match the password field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslkeyfile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if src:
        search_filter.append(['src', src])

    if password:
        search_filter.append(['password', password])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslkeyfile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslkeyfile')

    return response


def get_sslocspresponder(name=None, url=None, cache=None, cachetimeout=None, batchingdepth=None, batchingdelay=None,
                         resptimeout=None, respondercert=None, trustresponder=None, producedattimeskew=None,
                         signingcert=None, usenonce=None, insertclientcert=None):
    '''
    Show the running configuration for the sslocspresponder config key.

    name(str): Filters results that only match the name field.

    url(str): Filters results that only match the url field.

    cache(str): Filters results that only match the cache field.

    cachetimeout(int): Filters results that only match the cachetimeout field.

    batchingdepth(int): Filters results that only match the batchingdepth field.

    batchingdelay(int): Filters results that only match the batchingdelay field.

    resptimeout(int): Filters results that only match the resptimeout field.

    respondercert(str): Filters results that only match the respondercert field.

    trustresponder(bool): Filters results that only match the trustresponder field.

    producedattimeskew(int): Filters results that only match the producedattimeskew field.

    signingcert(str): Filters results that only match the signingcert field.

    usenonce(str): Filters results that only match the usenonce field.

    insertclientcert(str): Filters results that only match the insertclientcert field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslocspresponder

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if url:
        search_filter.append(['url', url])

    if cache:
        search_filter.append(['cache', cache])

    if cachetimeout:
        search_filter.append(['cachetimeout', cachetimeout])

    if batchingdepth:
        search_filter.append(['batchingdepth', batchingdepth])

    if batchingdelay:
        search_filter.append(['batchingdelay', batchingdelay])

    if resptimeout:
        search_filter.append(['resptimeout', resptimeout])

    if respondercert:
        search_filter.append(['respondercert', respondercert])

    if trustresponder:
        search_filter.append(['trustresponder', trustresponder])

    if producedattimeskew:
        search_filter.append(['producedattimeskew', producedattimeskew])

    if signingcert:
        search_filter.append(['signingcert', signingcert])

    if usenonce:
        search_filter.append(['usenonce', usenonce])

    if insertclientcert:
        search_filter.append(['insertclientcert', insertclientcert])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslocspresponder{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslocspresponder')

    return response


def get_sslparameter():
    '''
    Show the running configuration for the sslparameter config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslparameter

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslparameter'), 'sslparameter')

    return response


def get_sslpolicy(name=None, rule=None, reqaction=None, action=None, undefaction=None, comment=None):
    '''
    Show the running configuration for the sslpolicy config key.

    name(str): Filters results that only match the name field.

    rule(str): Filters results that only match the rule field.

    reqaction(str): Filters results that only match the reqaction field.

    action(str): Filters results that only match the action field.

    undefaction(str): Filters results that only match the undefaction field.

    comment(str): Filters results that only match the comment field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rule:
        search_filter.append(['rule', rule])

    if reqaction:
        search_filter.append(['reqaction', reqaction])

    if action:
        search_filter.append(['action', action])

    if undefaction:
        search_filter.append(['undefaction', undefaction])

    if comment:
        search_filter.append(['comment', comment])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy')

    return response


def get_sslpolicy_binding():
    '''
    Show the running configuration for the sslpolicy_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_binding'), 'sslpolicy_binding')

    return response


def get_sslpolicy_csvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the sslpolicy_csvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_csvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_csvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy_csvserver_binding')

    return response


def get_sslpolicy_lbvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the sslpolicy_lbvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_lbvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_lbvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy_lbvserver_binding')

    return response


def get_sslpolicy_sslglobal_binding(boundto=None, name=None):
    '''
    Show the running configuration for the sslpolicy_sslglobal_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_sslglobal_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_sslglobal_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy_sslglobal_binding')

    return response


def get_sslpolicy_sslpolicylabel_binding(boundto=None, name=None):
    '''
    Show the running configuration for the sslpolicy_sslpolicylabel_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_sslpolicylabel_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_sslpolicylabel_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy_sslpolicylabel_binding')

    return response


def get_sslpolicy_sslservice_binding(boundto=None, name=None):
    '''
    Show the running configuration for the sslpolicy_sslservice_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_sslservice_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_sslservice_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy_sslservice_binding')

    return response


def get_sslpolicy_sslvserver_binding(boundto=None, name=None):
    '''
    Show the running configuration for the sslpolicy_sslvserver_binding config key.

    boundto(str): Filters results that only match the boundto field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicy_sslvserver_binding

    '''

    search_filter = []

    if boundto:
        search_filter.append(['boundto', boundto])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicy_sslvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicy_sslvserver_binding')

    return response


def get_sslpolicylabel(labelname=None, ns_type=None):
    '''
    Show the running configuration for the sslpolicylabel config key.

    labelname(str): Filters results that only match the labelname field.

    ns_type(str): Filters results that only match the type field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicylabel

    '''

    search_filter = []

    if labelname:
        search_filter.append(['labelname', labelname])

    if ns_type:
        search_filter.append(['type', ns_type])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicylabel{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicylabel')

    return response


def get_sslpolicylabel_binding():
    '''
    Show the running configuration for the sslpolicylabel_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicylabel_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslpolicylabel_binding'), 'sslpolicylabel_binding')

    return response


def get_sslpolicylabel_sslpolicy_binding(priority=None, gotopriorityexpression=None, policyname=None, labeltype=None,
                                         labelname=None, invoke_labelname=None, invoke=None):
    '''
    Show the running configuration for the sslpolicylabel_sslpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    policyname(str): Filters results that only match the policyname field.

    labeltype(str): Filters results that only match the labeltype field.

    labelname(str): Filters results that only match the labelname field.

    invoke_labelname(str): Filters results that only match the invoke_labelname field.

    invoke(bool): Filters results that only match the invoke field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslpolicylabel_sslpolicy_binding

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
            __proxy__['citrixns.get']('config/sslpolicylabel_sslpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslpolicylabel_sslpolicy_binding')

    return response


def get_sslprofile(name=None, sslprofiletype=None, dhcount=None, dh=None, dhfile=None, ersa=None, ersacount=None,
                   sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None, clientauth=None,
                   clientcert=None, dhkeyexpsizelimit=None, sslredirect=None, redirectportrewrite=None, ssl3=None,
                   tls1=None, tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None,
                   commonname=None, pushenctrigger=None, sendclosenotify=None, cleartextport=None,
                   insertionencoding=None, denysslreneg=None, quantumsize=None, strictcachecks=None,
                   encrypttriggerpktcount=None, pushflag=None, dropreqwithnohostheader=None, pushenctriggertimeout=None,
                   ssltriggertimeout=None, clientauthuseboundcachain=None, sessionticket=None,
                   sessionticketlifetime=None, hsts=None, maxage=None, includesubdomains=None, ciphername=None,
                   cipherpriority=None, strictsigdigestcheck=None):
    '''
    Show the running configuration for the sslprofile config key.

    name(str): Filters results that only match the name field.

    sslprofiletype(str): Filters results that only match the sslprofiletype field.

    dhcount(int): Filters results that only match the dhcount field.

    dh(str): Filters results that only match the dh field.

    dhfile(str): Filters results that only match the dhfile field.

    ersa(str): Filters results that only match the ersa field.

    ersacount(int): Filters results that only match the ersacount field.

    sessreuse(str): Filters results that only match the sessreuse field.

    sesstimeout(int): Filters results that only match the sesstimeout field.

    cipherredirect(str): Filters results that only match the cipherredirect field.

    cipherurl(str): Filters results that only match the cipherurl field.

    clientauth(str): Filters results that only match the clientauth field.

    clientcert(str): Filters results that only match the clientcert field.

    dhkeyexpsizelimit(str): Filters results that only match the dhkeyexpsizelimit field.

    sslredirect(str): Filters results that only match the sslredirect field.

    redirectportrewrite(str): Filters results that only match the redirectportrewrite field.

    ssl3(str): Filters results that only match the ssl3 field.

    tls1(str): Filters results that only match the tls1 field.

    tls11(str): Filters results that only match the tls11 field.

    tls12(str): Filters results that only match the tls12 field.

    snienable(str): Filters results that only match the snienable field.

    ocspstapling(str): Filters results that only match the ocspstapling field.

    serverauth(str): Filters results that only match the serverauth field.

    commonname(str): Filters results that only match the commonname field.

    pushenctrigger(str): Filters results that only match the pushenctrigger field.

    sendclosenotify(str): Filters results that only match the sendclosenotify field.

    cleartextport(int): Filters results that only match the cleartextport field.

    insertionencoding(str): Filters results that only match the insertionencoding field.

    denysslreneg(str): Filters results that only match the denysslreneg field.

    quantumsize(str): Filters results that only match the quantumsize field.

    strictcachecks(str): Filters results that only match the strictcachecks field.

    encrypttriggerpktcount(int): Filters results that only match the encrypttriggerpktcount field.

    pushflag(int): Filters results that only match the pushflag field.

    dropreqwithnohostheader(str): Filters results that only match the dropreqwithnohostheader field.

    pushenctriggertimeout(int): Filters results that only match the pushenctriggertimeout field.

    ssltriggertimeout(int): Filters results that only match the ssltriggertimeout field.

    clientauthuseboundcachain(str): Filters results that only match the clientauthuseboundcachain field.

    sessionticket(str): Filters results that only match the sessionticket field.

    sessionticketlifetime(int): Filters results that only match the sessionticketlifetime field.

    hsts(str): Filters results that only match the hsts field.

    maxage(int): Filters results that only match the maxage field.

    includesubdomains(str): Filters results that only match the includesubdomains field.

    ciphername(str): Filters results that only match the ciphername field.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    strictsigdigestcheck(str): Filters results that only match the strictsigdigestcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if sslprofiletype:
        search_filter.append(['sslprofiletype', sslprofiletype])

    if dhcount:
        search_filter.append(['dhcount', dhcount])

    if dh:
        search_filter.append(['dh', dh])

    if dhfile:
        search_filter.append(['dhfile', dhfile])

    if ersa:
        search_filter.append(['ersa', ersa])

    if ersacount:
        search_filter.append(['ersacount', ersacount])

    if sessreuse:
        search_filter.append(['sessreuse', sessreuse])

    if sesstimeout:
        search_filter.append(['sesstimeout', sesstimeout])

    if cipherredirect:
        search_filter.append(['cipherredirect', cipherredirect])

    if cipherurl:
        search_filter.append(['cipherurl', cipherurl])

    if clientauth:
        search_filter.append(['clientauth', clientauth])

    if clientcert:
        search_filter.append(['clientcert', clientcert])

    if dhkeyexpsizelimit:
        search_filter.append(['dhkeyexpsizelimit', dhkeyexpsizelimit])

    if sslredirect:
        search_filter.append(['sslredirect', sslredirect])

    if redirectportrewrite:
        search_filter.append(['redirectportrewrite', redirectportrewrite])

    if ssl3:
        search_filter.append(['ssl3', ssl3])

    if tls1:
        search_filter.append(['tls1', tls1])

    if tls11:
        search_filter.append(['tls11', tls11])

    if tls12:
        search_filter.append(['tls12', tls12])

    if snienable:
        search_filter.append(['snienable', snienable])

    if ocspstapling:
        search_filter.append(['ocspstapling', ocspstapling])

    if serverauth:
        search_filter.append(['serverauth', serverauth])

    if commonname:
        search_filter.append(['commonname', commonname])

    if pushenctrigger:
        search_filter.append(['pushenctrigger', pushenctrigger])

    if sendclosenotify:
        search_filter.append(['sendclosenotify', sendclosenotify])

    if cleartextport:
        search_filter.append(['cleartextport', cleartextport])

    if insertionencoding:
        search_filter.append(['insertionencoding', insertionencoding])

    if denysslreneg:
        search_filter.append(['denysslreneg', denysslreneg])

    if quantumsize:
        search_filter.append(['quantumsize', quantumsize])

    if strictcachecks:
        search_filter.append(['strictcachecks', strictcachecks])

    if encrypttriggerpktcount:
        search_filter.append(['encrypttriggerpktcount', encrypttriggerpktcount])

    if pushflag:
        search_filter.append(['pushflag', pushflag])

    if dropreqwithnohostheader:
        search_filter.append(['dropreqwithnohostheader', dropreqwithnohostheader])

    if pushenctriggertimeout:
        search_filter.append(['pushenctriggertimeout', pushenctriggertimeout])

    if ssltriggertimeout:
        search_filter.append(['ssltriggertimeout', ssltriggertimeout])

    if clientauthuseboundcachain:
        search_filter.append(['clientauthuseboundcachain', clientauthuseboundcachain])

    if sessionticket:
        search_filter.append(['sessionticket', sessionticket])

    if sessionticketlifetime:
        search_filter.append(['sessionticketlifetime', sessionticketlifetime])

    if hsts:
        search_filter.append(['hsts', hsts])

    if maxage:
        search_filter.append(['maxage', maxage])

    if includesubdomains:
        search_filter.append(['includesubdomains', includesubdomains])

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if strictsigdigestcheck:
        search_filter.append(['strictsigdigestcheck', strictsigdigestcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslprofile')

    return response


def get_sslprofile_binding():
    '''
    Show the running configuration for the sslprofile_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile_binding'), 'sslprofile_binding')

    return response


def get_sslprofile_ecccurve_binding(cipherpriority=None, name=None, ecccurvename=None):
    '''
    Show the running configuration for the sslprofile_ecccurve_binding config key.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    name(str): Filters results that only match the name field.

    ecccurvename(str): Filters results that only match the ecccurvename field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile_ecccurve_binding

    '''

    search_filter = []

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if name:
        search_filter.append(['name', name])

    if ecccurvename:
        search_filter.append(['ecccurvename', ecccurvename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile_ecccurve_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslprofile_ecccurve_binding')

    return response


def get_sslprofile_sslcertkey_binding(cipherpriority=None, name=None):
    '''
    Show the running configuration for the sslprofile_sslcertkey_binding config key.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    name(str): Filters results that only match the name field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile_sslcertkey_binding

    '''

    search_filter = []

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if name:
        search_filter.append(['name', name])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile_sslcertkey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslprofile_sslcertkey_binding')

    return response


def get_sslprofile_sslcipher_binding(ciphername=None, cipheraliasname=None, cipherpriority=None, name=None,
                                     description=None):
    '''
    Show the running configuration for the sslprofile_sslcipher_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    cipheraliasname(str): Filters results that only match the cipheraliasname field.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    name(str): Filters results that only match the name field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile_sslcipher_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipheraliasname:
        search_filter.append(['cipheraliasname', cipheraliasname])

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if name:
        search_filter.append(['name', name])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile_sslcipher_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslprofile_sslcipher_binding')

    return response


def get_sslprofile_sslciphersuite_binding(ciphername=None, cipherpriority=None, name=None, description=None):
    '''
    Show the running configuration for the sslprofile_sslciphersuite_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    name(str): Filters results that only match the name field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile_sslciphersuite_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if name:
        search_filter.append(['name', name])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile_sslciphersuite_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslprofile_sslciphersuite_binding')

    return response


def get_sslprofile_sslvserver_binding(cipherpriority=None, name=None, description=None, servicename=None):
    '''
    Show the running configuration for the sslprofile_sslvserver_binding config key.

    cipherpriority(int): Filters results that only match the cipherpriority field.

    name(str): Filters results that only match the name field.

    description(str): Filters results that only match the description field.

    servicename(str): Filters results that only match the servicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslprofile_sslvserver_binding

    '''

    search_filter = []

    if cipherpriority:
        search_filter.append(['cipherpriority', cipherpriority])

    if name:
        search_filter.append(['name', name])

    if description:
        search_filter.append(['description', description])

    if servicename:
        search_filter.append(['servicename', servicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslprofile_sslvserver_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslprofile_sslvserver_binding')

    return response


def get_sslservice(servicename=None, dh=None, dhfile=None, dhcount=None, dhkeyexpsizelimit=None, ersa=None,
                   ersacount=None, sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None,
                   sslv2redirect=None, sslv2url=None, clientauth=None, clientcert=None, sslredirect=None,
                   redirectportrewrite=None, ssl2=None, ssl3=None, tls1=None, tls11=None, tls12=None, snienable=None,
                   ocspstapling=None, serverauth=None, commonname=None, pushenctrigger=None, sendclosenotify=None,
                   dtlsprofilename=None, sslprofile=None, strictsigdigestcheck=None):
    '''
    Show the running configuration for the sslservice config key.

    servicename(str): Filters results that only match the servicename field.

    dh(str): Filters results that only match the dh field.

    dhfile(str): Filters results that only match the dhfile field.

    dhcount(int): Filters results that only match the dhcount field.

    dhkeyexpsizelimit(str): Filters results that only match the dhkeyexpsizelimit field.

    ersa(str): Filters results that only match the ersa field.

    ersacount(int): Filters results that only match the ersacount field.

    sessreuse(str): Filters results that only match the sessreuse field.

    sesstimeout(int): Filters results that only match the sesstimeout field.

    cipherredirect(str): Filters results that only match the cipherredirect field.

    cipherurl(str): Filters results that only match the cipherurl field.

    sslv2redirect(str): Filters results that only match the sslv2redirect field.

    sslv2url(str): Filters results that only match the sslv2url field.

    clientauth(str): Filters results that only match the clientauth field.

    clientcert(str): Filters results that only match the clientcert field.

    sslredirect(str): Filters results that only match the sslredirect field.

    redirectportrewrite(str): Filters results that only match the redirectportrewrite field.

    ssl2(str): Filters results that only match the ssl2 field.

    ssl3(str): Filters results that only match the ssl3 field.

    tls1(str): Filters results that only match the tls1 field.

    tls11(str): Filters results that only match the tls11 field.

    tls12(str): Filters results that only match the tls12 field.

    snienable(str): Filters results that only match the snienable field.

    ocspstapling(str): Filters results that only match the ocspstapling field.

    serverauth(str): Filters results that only match the serverauth field.

    commonname(str): Filters results that only match the commonname field.

    pushenctrigger(str): Filters results that only match the pushenctrigger field.

    sendclosenotify(str): Filters results that only match the sendclosenotify field.

    dtlsprofilename(str): Filters results that only match the dtlsprofilename field.

    sslprofile(str): Filters results that only match the sslprofile field.

    strictsigdigestcheck(str): Filters results that only match the strictsigdigestcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice

    '''

    search_filter = []

    if servicename:
        search_filter.append(['servicename', servicename])

    if dh:
        search_filter.append(['dh', dh])

    if dhfile:
        search_filter.append(['dhfile', dhfile])

    if dhcount:
        search_filter.append(['dhcount', dhcount])

    if dhkeyexpsizelimit:
        search_filter.append(['dhkeyexpsizelimit', dhkeyexpsizelimit])

    if ersa:
        search_filter.append(['ersa', ersa])

    if ersacount:
        search_filter.append(['ersacount', ersacount])

    if sessreuse:
        search_filter.append(['sessreuse', sessreuse])

    if sesstimeout:
        search_filter.append(['sesstimeout', sesstimeout])

    if cipherredirect:
        search_filter.append(['cipherredirect', cipherredirect])

    if cipherurl:
        search_filter.append(['cipherurl', cipherurl])

    if sslv2redirect:
        search_filter.append(['sslv2redirect', sslv2redirect])

    if sslv2url:
        search_filter.append(['sslv2url', sslv2url])

    if clientauth:
        search_filter.append(['clientauth', clientauth])

    if clientcert:
        search_filter.append(['clientcert', clientcert])

    if sslredirect:
        search_filter.append(['sslredirect', sslredirect])

    if redirectportrewrite:
        search_filter.append(['redirectportrewrite', redirectportrewrite])

    if ssl2:
        search_filter.append(['ssl2', ssl2])

    if ssl3:
        search_filter.append(['ssl3', ssl3])

    if tls1:
        search_filter.append(['tls1', tls1])

    if tls11:
        search_filter.append(['tls11', tls11])

    if tls12:
        search_filter.append(['tls12', tls12])

    if snienable:
        search_filter.append(['snienable', snienable])

    if ocspstapling:
        search_filter.append(['ocspstapling', ocspstapling])

    if serverauth:
        search_filter.append(['serverauth', serverauth])

    if commonname:
        search_filter.append(['commonname', commonname])

    if pushenctrigger:
        search_filter.append(['pushenctrigger', pushenctrigger])

    if sendclosenotify:
        search_filter.append(['sendclosenotify', sendclosenotify])

    if dtlsprofilename:
        search_filter.append(['dtlsprofilename', dtlsprofilename])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    if strictsigdigestcheck:
        search_filter.append(['strictsigdigestcheck', strictsigdigestcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservice')

    return response


def get_sslservice_binding():
    '''
    Show the running configuration for the sslservice_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice_binding'), 'sslservice_binding')

    return response


def get_sslservice_ecccurve_binding(ecccurvename=None, servicename=None):
    '''
    Show the running configuration for the sslservice_ecccurve_binding config key.

    ecccurvename(str): Filters results that only match the ecccurvename field.

    servicename(str): Filters results that only match the servicename field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice_ecccurve_binding

    '''

    search_filter = []

    if ecccurvename:
        search_filter.append(['ecccurvename', ecccurvename])

    if servicename:
        search_filter.append(['servicename', servicename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice_ecccurve_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservice_ecccurve_binding')

    return response


def get_sslservice_sslcertkey_binding(ca=None, crlcheck=None, servicename=None, certkeyname=None, skipcaname=None,
                                      snicert=None, ocspcheck=None):
    '''
    Show the running configuration for the sslservice_sslcertkey_binding config key.

    ca(bool): Filters results that only match the ca field.

    crlcheck(str): Filters results that only match the crlcheck field.

    servicename(str): Filters results that only match the servicename field.

    certkeyname(str): Filters results that only match the certkeyname field.

    skipcaname(bool): Filters results that only match the skipcaname field.

    snicert(bool): Filters results that only match the snicert field.

    ocspcheck(str): Filters results that only match the ocspcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice_sslcertkey_binding

    '''

    search_filter = []

    if ca:
        search_filter.append(['ca', ca])

    if crlcheck:
        search_filter.append(['crlcheck', crlcheck])

    if servicename:
        search_filter.append(['servicename', servicename])

    if certkeyname:
        search_filter.append(['certkeyname', certkeyname])

    if skipcaname:
        search_filter.append(['skipcaname', skipcaname])

    if snicert:
        search_filter.append(['snicert', snicert])

    if ocspcheck:
        search_filter.append(['ocspcheck', ocspcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice_sslcertkey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservice_sslcertkey_binding')

    return response


def get_sslservice_sslcipher_binding(ciphername=None, cipheraliasname=None, servicename=None, description=None):
    '''
    Show the running configuration for the sslservice_sslcipher_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    cipheraliasname(str): Filters results that only match the cipheraliasname field.

    servicename(str): Filters results that only match the servicename field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice_sslcipher_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipheraliasname:
        search_filter.append(['cipheraliasname', cipheraliasname])

    if servicename:
        search_filter.append(['servicename', servicename])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice_sslcipher_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservice_sslcipher_binding')

    return response


def get_sslservice_sslciphersuite_binding(ciphername=None, servicename=None, description=None):
    '''
    Show the running configuration for the sslservice_sslciphersuite_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    servicename(str): Filters results that only match the servicename field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice_sslciphersuite_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if servicename:
        search_filter.append(['servicename', servicename])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice_sslciphersuite_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservice_sslciphersuite_binding')

    return response


def get_sslservice_sslpolicy_binding(priority=None, policyname=None, labelname=None, servicename=None,
                                     gotopriorityexpression=None, invoke=None, labeltype=None):
    '''
    Show the running configuration for the sslservice_sslpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    servicename(str): Filters results that only match the servicename field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservice_sslpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if servicename:
        search_filter.append(['servicename', servicename])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservice_sslpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservice_sslpolicy_binding')

    return response


def get_sslservicegroup(servicegroupname=None, sslprofile=None, sessreuse=None, sesstimeout=None, ssl3=None, tls1=None,
                        tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None, commonname=None,
                        sendclosenotify=None, strictsigdigestcheck=None):
    '''
    Show the running configuration for the sslservicegroup config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    sslprofile(str): Filters results that only match the sslprofile field.

    sessreuse(str): Filters results that only match the sessreuse field.

    sesstimeout(int): Filters results that only match the sesstimeout field.

    ssl3(str): Filters results that only match the ssl3 field.

    tls1(str): Filters results that only match the tls1 field.

    tls11(str): Filters results that only match the tls11 field.

    tls12(str): Filters results that only match the tls12 field.

    snienable(str): Filters results that only match the snienable field.

    ocspstapling(str): Filters results that only match the ocspstapling field.

    serverauth(str): Filters results that only match the serverauth field.

    commonname(str): Filters results that only match the commonname field.

    sendclosenotify(str): Filters results that only match the sendclosenotify field.

    strictsigdigestcheck(str): Filters results that only match the strictsigdigestcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservicegroup

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    if sessreuse:
        search_filter.append(['sessreuse', sessreuse])

    if sesstimeout:
        search_filter.append(['sesstimeout', sesstimeout])

    if ssl3:
        search_filter.append(['ssl3', ssl3])

    if tls1:
        search_filter.append(['tls1', tls1])

    if tls11:
        search_filter.append(['tls11', tls11])

    if tls12:
        search_filter.append(['tls12', tls12])

    if snienable:
        search_filter.append(['snienable', snienable])

    if ocspstapling:
        search_filter.append(['ocspstapling', ocspstapling])

    if serverauth:
        search_filter.append(['serverauth', serverauth])

    if commonname:
        search_filter.append(['commonname', commonname])

    if sendclosenotify:
        search_filter.append(['sendclosenotify', sendclosenotify])

    if strictsigdigestcheck:
        search_filter.append(['strictsigdigestcheck', strictsigdigestcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservicegroup{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservicegroup')

    return response


def get_sslservicegroup_binding():
    '''
    Show the running configuration for the sslservicegroup_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservicegroup_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservicegroup_binding'), 'sslservicegroup_binding')

    return response


def get_sslservicegroup_ecccurve_binding(servicegroupname=None, ecccurvename=None):
    '''
    Show the running configuration for the sslservicegroup_ecccurve_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    ecccurvename(str): Filters results that only match the ecccurvename field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservicegroup_ecccurve_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if ecccurvename:
        search_filter.append(['ecccurvename', ecccurvename])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservicegroup_ecccurve_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservicegroup_ecccurve_binding')

    return response


def get_sslservicegroup_sslcertkey_binding(servicegroupname=None, ca=None, crlcheck=None, certkeyname=None, snicert=None,
                                           ocspcheck=None):
    '''
    Show the running configuration for the sslservicegroup_sslcertkey_binding config key.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    ca(bool): Filters results that only match the ca field.

    crlcheck(str): Filters results that only match the crlcheck field.

    certkeyname(str): Filters results that only match the certkeyname field.

    snicert(bool): Filters results that only match the snicert field.

    ocspcheck(str): Filters results that only match the ocspcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservicegroup_sslcertkey_binding

    '''

    search_filter = []

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if ca:
        search_filter.append(['ca', ca])

    if crlcheck:
        search_filter.append(['crlcheck', crlcheck])

    if certkeyname:
        search_filter.append(['certkeyname', certkeyname])

    if snicert:
        search_filter.append(['snicert', snicert])

    if ocspcheck:
        search_filter.append(['ocspcheck', ocspcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservicegroup_sslcertkey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservicegroup_sslcertkey_binding')

    return response


def get_sslservicegroup_sslcipher_binding(ciphername=None, cipheraliasname=None, servicegroupname=None,
                                          description=None):
    '''
    Show the running configuration for the sslservicegroup_sslcipher_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    cipheraliasname(str): Filters results that only match the cipheraliasname field.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservicegroup_sslcipher_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipheraliasname:
        search_filter.append(['cipheraliasname', cipheraliasname])

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservicegroup_sslcipher_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservicegroup_sslcipher_binding')

    return response


def get_sslservicegroup_sslciphersuite_binding(ciphername=None, servicegroupname=None, description=None):
    '''
    Show the running configuration for the sslservicegroup_sslciphersuite_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    servicegroupname(str): Filters results that only match the servicegroupname field.

    description(str): Filters results that only match the description field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslservicegroup_sslciphersuite_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if servicegroupname:
        search_filter.append(['servicegroupname', servicegroupname])

    if description:
        search_filter.append(['description', description])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslservicegroup_sslciphersuite_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslservicegroup_sslciphersuite_binding')

    return response


def get_sslvserver(vservername=None, cleartextport=None, dh=None, dhfile=None, dhcount=None, dhkeyexpsizelimit=None,
                   ersa=None, ersacount=None, sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None,
                   sslv2redirect=None, sslv2url=None, clientauth=None, clientcert=None, sslredirect=None,
                   redirectportrewrite=None, ssl2=None, ssl3=None, tls1=None, tls11=None, tls12=None, snienable=None,
                   ocspstapling=None, pushenctrigger=None, sendclosenotify=None, dtlsprofilename=None, sslprofile=None,
                   hsts=None, maxage=None, includesubdomains=None, strictsigdigestcheck=None):
    '''
    Show the running configuration for the sslvserver config key.

    vservername(str): Filters results that only match the vservername field.

    cleartextport(int): Filters results that only match the cleartextport field.

    dh(str): Filters results that only match the dh field.

    dhfile(str): Filters results that only match the dhfile field.

    dhcount(int): Filters results that only match the dhcount field.

    dhkeyexpsizelimit(str): Filters results that only match the dhkeyexpsizelimit field.

    ersa(str): Filters results that only match the ersa field.

    ersacount(int): Filters results that only match the ersacount field.

    sessreuse(str): Filters results that only match the sessreuse field.

    sesstimeout(int): Filters results that only match the sesstimeout field.

    cipherredirect(str): Filters results that only match the cipherredirect field.

    cipherurl(str): Filters results that only match the cipherurl field.

    sslv2redirect(str): Filters results that only match the sslv2redirect field.

    sslv2url(str): Filters results that only match the sslv2url field.

    clientauth(str): Filters results that only match the clientauth field.

    clientcert(str): Filters results that only match the clientcert field.

    sslredirect(str): Filters results that only match the sslredirect field.

    redirectportrewrite(str): Filters results that only match the redirectportrewrite field.

    ssl2(str): Filters results that only match the ssl2 field.

    ssl3(str): Filters results that only match the ssl3 field.

    tls1(str): Filters results that only match the tls1 field.

    tls11(str): Filters results that only match the tls11 field.

    tls12(str): Filters results that only match the tls12 field.

    snienable(str): Filters results that only match the snienable field.

    ocspstapling(str): Filters results that only match the ocspstapling field.

    pushenctrigger(str): Filters results that only match the pushenctrigger field.

    sendclosenotify(str): Filters results that only match the sendclosenotify field.

    dtlsprofilename(str): Filters results that only match the dtlsprofilename field.

    sslprofile(str): Filters results that only match the sslprofile field.

    hsts(str): Filters results that only match the hsts field.

    maxage(int): Filters results that only match the maxage field.

    includesubdomains(str): Filters results that only match the includesubdomains field.

    strictsigdigestcheck(str): Filters results that only match the strictsigdigestcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver

    '''

    search_filter = []

    if vservername:
        search_filter.append(['vservername', vservername])

    if cleartextport:
        search_filter.append(['cleartextport', cleartextport])

    if dh:
        search_filter.append(['dh', dh])

    if dhfile:
        search_filter.append(['dhfile', dhfile])

    if dhcount:
        search_filter.append(['dhcount', dhcount])

    if dhkeyexpsizelimit:
        search_filter.append(['dhkeyexpsizelimit', dhkeyexpsizelimit])

    if ersa:
        search_filter.append(['ersa', ersa])

    if ersacount:
        search_filter.append(['ersacount', ersacount])

    if sessreuse:
        search_filter.append(['sessreuse', sessreuse])

    if sesstimeout:
        search_filter.append(['sesstimeout', sesstimeout])

    if cipherredirect:
        search_filter.append(['cipherredirect', cipherredirect])

    if cipherurl:
        search_filter.append(['cipherurl', cipherurl])

    if sslv2redirect:
        search_filter.append(['sslv2redirect', sslv2redirect])

    if sslv2url:
        search_filter.append(['sslv2url', sslv2url])

    if clientauth:
        search_filter.append(['clientauth', clientauth])

    if clientcert:
        search_filter.append(['clientcert', clientcert])

    if sslredirect:
        search_filter.append(['sslredirect', sslredirect])

    if redirectportrewrite:
        search_filter.append(['redirectportrewrite', redirectportrewrite])

    if ssl2:
        search_filter.append(['ssl2', ssl2])

    if ssl3:
        search_filter.append(['ssl3', ssl3])

    if tls1:
        search_filter.append(['tls1', tls1])

    if tls11:
        search_filter.append(['tls11', tls11])

    if tls12:
        search_filter.append(['tls12', tls12])

    if snienable:
        search_filter.append(['snienable', snienable])

    if ocspstapling:
        search_filter.append(['ocspstapling', ocspstapling])

    if pushenctrigger:
        search_filter.append(['pushenctrigger', pushenctrigger])

    if sendclosenotify:
        search_filter.append(['sendclosenotify', sendclosenotify])

    if dtlsprofilename:
        search_filter.append(['dtlsprofilename', dtlsprofilename])

    if sslprofile:
        search_filter.append(['sslprofile', sslprofile])

    if hsts:
        search_filter.append(['hsts', hsts])

    if maxage:
        search_filter.append(['maxage', maxage])

    if includesubdomains:
        search_filter.append(['includesubdomains', includesubdomains])

    if strictsigdigestcheck:
        search_filter.append(['strictsigdigestcheck', strictsigdigestcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslvserver')

    return response


def get_sslvserver_binding():
    '''
    Show the running configuration for the sslvserver_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver_binding'), 'sslvserver_binding')

    return response


def get_sslvserver_ecccurve_binding(ecccurvename=None, vservername=None):
    '''
    Show the running configuration for the sslvserver_ecccurve_binding config key.

    ecccurvename(str): Filters results that only match the ecccurvename field.

    vservername(str): Filters results that only match the vservername field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver_ecccurve_binding

    '''

    search_filter = []

    if ecccurvename:
        search_filter.append(['ecccurvename', ecccurvename])

    if vservername:
        search_filter.append(['vservername', vservername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver_ecccurve_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslvserver_ecccurve_binding')

    return response


def get_sslvserver_sslcertkey_binding(ca=None, crlcheck=None, vservername=None, certkeyname=None, skipcaname=None,
                                      snicert=None, ocspcheck=None):
    '''
    Show the running configuration for the sslvserver_sslcertkey_binding config key.

    ca(bool): Filters results that only match the ca field.

    crlcheck(str): Filters results that only match the crlcheck field.

    vservername(str): Filters results that only match the vservername field.

    certkeyname(str): Filters results that only match the certkeyname field.

    skipcaname(bool): Filters results that only match the skipcaname field.

    snicert(bool): Filters results that only match the snicert field.

    ocspcheck(str): Filters results that only match the ocspcheck field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver_sslcertkey_binding

    '''

    search_filter = []

    if ca:
        search_filter.append(['ca', ca])

    if crlcheck:
        search_filter.append(['crlcheck', crlcheck])

    if vservername:
        search_filter.append(['vservername', vservername])

    if certkeyname:
        search_filter.append(['certkeyname', certkeyname])

    if skipcaname:
        search_filter.append(['skipcaname', skipcaname])

    if snicert:
        search_filter.append(['snicert', snicert])

    if ocspcheck:
        search_filter.append(['ocspcheck', ocspcheck])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver_sslcertkey_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslvserver_sslcertkey_binding')

    return response


def get_sslvserver_sslcipher_binding(ciphername=None, cipheraliasname=None, description=None, vservername=None):
    '''
    Show the running configuration for the sslvserver_sslcipher_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    cipheraliasname(str): Filters results that only match the cipheraliasname field.

    description(str): Filters results that only match the description field.

    vservername(str): Filters results that only match the vservername field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver_sslcipher_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if cipheraliasname:
        search_filter.append(['cipheraliasname', cipheraliasname])

    if description:
        search_filter.append(['description', description])

    if vservername:
        search_filter.append(['vservername', vservername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver_sslcipher_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslvserver_sslcipher_binding')

    return response


def get_sslvserver_sslciphersuite_binding(ciphername=None, description=None, vservername=None):
    '''
    Show the running configuration for the sslvserver_sslciphersuite_binding config key.

    ciphername(str): Filters results that only match the ciphername field.

    description(str): Filters results that only match the description field.

    vservername(str): Filters results that only match the vservername field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver_sslciphersuite_binding

    '''

    search_filter = []

    if ciphername:
        search_filter.append(['ciphername', ciphername])

    if description:
        search_filter.append(['description', description])

    if vservername:
        search_filter.append(['vservername', vservername])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver_sslciphersuite_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslvserver_sslciphersuite_binding')

    return response


def get_sslvserver_sslpolicy_binding(priority=None, policyname=None, labelname=None, vservername=None,
                                     gotopriorityexpression=None, invoke=None, ns_type=None, labeltype=None):
    '''
    Show the running configuration for the sslvserver_sslpolicy_binding config key.

    priority(int): Filters results that only match the priority field.

    policyname(str): Filters results that only match the policyname field.

    labelname(str): Filters results that only match the labelname field.

    vservername(str): Filters results that only match the vservername field.

    gotopriorityexpression(str): Filters results that only match the gotopriorityexpression field.

    invoke(bool): Filters results that only match the invoke field.

    ns_type(str): Filters results that only match the type field.

    labeltype(str): Filters results that only match the labeltype field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslvserver_sslpolicy_binding

    '''

    search_filter = []

    if priority:
        search_filter.append(['priority', priority])

    if policyname:
        search_filter.append(['policyname', policyname])

    if labelname:
        search_filter.append(['labelname', labelname])

    if vservername:
        search_filter.append(['vservername', vservername])

    if gotopriorityexpression:
        search_filter.append(['gotopriorityexpression', gotopriorityexpression])

    if invoke:
        search_filter.append(['invoke', invoke])

    if ns_type:
        search_filter.append(['type', ns_type])

    if labeltype:
        search_filter.append(['labeltype', labeltype])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslvserver_sslpolicy_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslvserver_sslpolicy_binding')

    return response


def get_sslwrapkey(wrapkeyname=None, password=None, salt=None):
    '''
    Show the running configuration for the sslwrapkey config key.

    wrapkeyname(str): Filters results that only match the wrapkeyname field.

    password(str): Filters results that only match the password field.

    salt(str): Filters results that only match the salt field.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.get_sslwrapkey

    '''

    search_filter = []

    if wrapkeyname:
        search_filter.append(['wrapkeyname', wrapkeyname])

    if password:
        search_filter.append(['password', password])

    if salt:
        search_filter.append(['salt', salt])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/sslwrapkey{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'sslwrapkey')

    return response


def unset_sslcertkey(certkey=None, cert=None, key=None, password=None, fipskey=None, hsmkey=None, inform=None,
                     passplain=None, expirymonitor=None, notificationperiod=None, bundle=None, linkcertkeyname=None,
                     nodomaincheck=None, save=False):
    '''
    Unsets values from the sslcertkey configuration key.

    certkey(bool): Unsets the certkey value.

    cert(bool): Unsets the cert value.

    key(bool): Unsets the key value.

    password(bool): Unsets the password value.

    fipskey(bool): Unsets the fipskey value.

    hsmkey(bool): Unsets the hsmkey value.

    inform(bool): Unsets the inform value.

    passplain(bool): Unsets the passplain value.

    expirymonitor(bool): Unsets the expirymonitor value.

    notificationperiod(bool): Unsets the notificationperiod value.

    bundle(bool): Unsets the bundle value.

    linkcertkeyname(bool): Unsets the linkcertkeyname value.

    nodomaincheck(bool): Unsets the nodomaincheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslcertkey <args>

    '''

    result = {}

    payload = {'sslcertkey': {}}

    if certkey:
        payload['sslcertkey']['certkey'] = True

    if cert:
        payload['sslcertkey']['cert'] = True

    if key:
        payload['sslcertkey']['key'] = True

    if password:
        payload['sslcertkey']['password'] = True

    if fipskey:
        payload['sslcertkey']['fipskey'] = True

    if hsmkey:
        payload['sslcertkey']['hsmkey'] = True

    if inform:
        payload['sslcertkey']['inform'] = True

    if passplain:
        payload['sslcertkey']['passplain'] = True

    if expirymonitor:
        payload['sslcertkey']['expirymonitor'] = True

    if notificationperiod:
        payload['sslcertkey']['notificationperiod'] = True

    if bundle:
        payload['sslcertkey']['bundle'] = True

    if linkcertkeyname:
        payload['sslcertkey']['linkcertkeyname'] = True

    if nodomaincheck:
        payload['sslcertkey']['nodomaincheck'] = True

    execution = __proxy__['citrixns.post']('config/sslcertkey?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslcipher(ciphergroupname=None, ciphgrpalias=None, ciphername=None, cipherpriority=None, sslprofile=None,
                    save=False):
    '''
    Unsets values from the sslcipher configuration key.

    ciphergroupname(bool): Unsets the ciphergroupname value.

    ciphgrpalias(bool): Unsets the ciphgrpalias value.

    ciphername(bool): Unsets the ciphername value.

    cipherpriority(bool): Unsets the cipherpriority value.

    sslprofile(bool): Unsets the sslprofile value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslcipher <args>

    '''

    result = {}

    payload = {'sslcipher': {}}

    if ciphergroupname:
        payload['sslcipher']['ciphergroupname'] = True

    if ciphgrpalias:
        payload['sslcipher']['ciphgrpalias'] = True

    if ciphername:
        payload['sslcipher']['ciphername'] = True

    if cipherpriority:
        payload['sslcipher']['cipherpriority'] = True

    if sslprofile:
        payload['sslcipher']['sslprofile'] = True

    execution = __proxy__['citrixns.post']('config/sslcipher?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslcrl(crlname=None, crlpath=None, inform=None, refresh=None, cacert=None, method=None, server=None, url=None,
                 port=None, basedn=None, scope=None, interval=None, day=None, time=None, binddn=None, password=None,
                 binary=None, cacertfile=None, cakeyfile=None, indexfile=None, revoke=None, gencrl=None, save=False):
    '''
    Unsets values from the sslcrl configuration key.

    crlname(bool): Unsets the crlname value.

    crlpath(bool): Unsets the crlpath value.

    inform(bool): Unsets the inform value.

    refresh(bool): Unsets the refresh value.

    cacert(bool): Unsets the cacert value.

    method(bool): Unsets the method value.

    server(bool): Unsets the server value.

    url(bool): Unsets the url value.

    port(bool): Unsets the port value.

    basedn(bool): Unsets the basedn value.

    scope(bool): Unsets the scope value.

    interval(bool): Unsets the interval value.

    day(bool): Unsets the day value.

    time(bool): Unsets the time value.

    binddn(bool): Unsets the binddn value.

    password(bool): Unsets the password value.

    binary(bool): Unsets the binary value.

    cacertfile(bool): Unsets the cacertfile value.

    cakeyfile(bool): Unsets the cakeyfile value.

    indexfile(bool): Unsets the indexfile value.

    revoke(bool): Unsets the revoke value.

    gencrl(bool): Unsets the gencrl value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslcrl <args>

    '''

    result = {}

    payload = {'sslcrl': {}}

    if crlname:
        payload['sslcrl']['crlname'] = True

    if crlpath:
        payload['sslcrl']['crlpath'] = True

    if inform:
        payload['sslcrl']['inform'] = True

    if refresh:
        payload['sslcrl']['refresh'] = True

    if cacert:
        payload['sslcrl']['cacert'] = True

    if method:
        payload['sslcrl']['method'] = True

    if server:
        payload['sslcrl']['server'] = True

    if url:
        payload['sslcrl']['url'] = True

    if port:
        payload['sslcrl']['port'] = True

    if basedn:
        payload['sslcrl']['basedn'] = True

    if scope:
        payload['sslcrl']['scope'] = True

    if interval:
        payload['sslcrl']['interval'] = True

    if day:
        payload['sslcrl']['day'] = True

    if time:
        payload['sslcrl']['time'] = True

    if binddn:
        payload['sslcrl']['binddn'] = True

    if password:
        payload['sslcrl']['password'] = True

    if binary:
        payload['sslcrl']['binary'] = True

    if cacertfile:
        payload['sslcrl']['cacertfile'] = True

    if cakeyfile:
        payload['sslcrl']['cakeyfile'] = True

    if indexfile:
        payload['sslcrl']['indexfile'] = True

    if revoke:
        payload['sslcrl']['revoke'] = True

    if gencrl:
        payload['sslcrl']['gencrl'] = True

    execution = __proxy__['citrixns.post']('config/sslcrl?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_ssldtlsprofile(name=None, pmtudiscovery=None, maxrecordsize=None, maxretrytime=None, helloverifyrequest=None,
                         terminatesession=None, maxpacketsize=None, save=False):
    '''
    Unsets values from the ssldtlsprofile configuration key.

    name(bool): Unsets the name value.

    pmtudiscovery(bool): Unsets the pmtudiscovery value.

    maxrecordsize(bool): Unsets the maxrecordsize value.

    maxretrytime(bool): Unsets the maxretrytime value.

    helloverifyrequest(bool): Unsets the helloverifyrequest value.

    terminatesession(bool): Unsets the terminatesession value.

    maxpacketsize(bool): Unsets the maxpacketsize value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_ssldtlsprofile <args>

    '''

    result = {}

    payload = {'ssldtlsprofile': {}}

    if name:
        payload['ssldtlsprofile']['name'] = True

    if pmtudiscovery:
        payload['ssldtlsprofile']['pmtudiscovery'] = True

    if maxrecordsize:
        payload['ssldtlsprofile']['maxrecordsize'] = True

    if maxretrytime:
        payload['ssldtlsprofile']['maxretrytime'] = True

    if helloverifyrequest:
        payload['ssldtlsprofile']['helloverifyrequest'] = True

    if terminatesession:
        payload['ssldtlsprofile']['terminatesession'] = True

    if maxpacketsize:
        payload['ssldtlsprofile']['maxpacketsize'] = True

    execution = __proxy__['citrixns.post']('config/ssldtlsprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslfips(inithsm=None, sopassword=None, oldsopassword=None, userpassword=None, hsmlabel=None, fipsfw=None,
                  save=False):
    '''
    Unsets values from the sslfips configuration key.

    inithsm(bool): Unsets the inithsm value.

    sopassword(bool): Unsets the sopassword value.

    oldsopassword(bool): Unsets the oldsopassword value.

    userpassword(bool): Unsets the userpassword value.

    hsmlabel(bool): Unsets the hsmlabel value.

    fipsfw(bool): Unsets the fipsfw value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslfips <args>

    '''

    result = {}

    payload = {'sslfips': {}}

    if inithsm:
        payload['sslfips']['inithsm'] = True

    if sopassword:
        payload['sslfips']['sopassword'] = True

    if oldsopassword:
        payload['sslfips']['oldsopassword'] = True

    if userpassword:
        payload['sslfips']['userpassword'] = True

    if hsmlabel:
        payload['sslfips']['hsmlabel'] = True

    if fipsfw:
        payload['sslfips']['fipsfw'] = True

    execution = __proxy__['citrixns.post']('config/sslfips?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslocspresponder(name=None, url=None, cache=None, cachetimeout=None, batchingdepth=None, batchingdelay=None,
                           resptimeout=None, respondercert=None, trustresponder=None, producedattimeskew=None,
                           signingcert=None, usenonce=None, insertclientcert=None, save=False):
    '''
    Unsets values from the sslocspresponder configuration key.

    name(bool): Unsets the name value.

    url(bool): Unsets the url value.

    cache(bool): Unsets the cache value.

    cachetimeout(bool): Unsets the cachetimeout value.

    batchingdepth(bool): Unsets the batchingdepth value.

    batchingdelay(bool): Unsets the batchingdelay value.

    resptimeout(bool): Unsets the resptimeout value.

    respondercert(bool): Unsets the respondercert value.

    trustresponder(bool): Unsets the trustresponder value.

    producedattimeskew(bool): Unsets the producedattimeskew value.

    signingcert(bool): Unsets the signingcert value.

    usenonce(bool): Unsets the usenonce value.

    insertclientcert(bool): Unsets the insertclientcert value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslocspresponder <args>

    '''

    result = {}

    payload = {'sslocspresponder': {}}

    if name:
        payload['sslocspresponder']['name'] = True

    if url:
        payload['sslocspresponder']['url'] = True

    if cache:
        payload['sslocspresponder']['cache'] = True

    if cachetimeout:
        payload['sslocspresponder']['cachetimeout'] = True

    if batchingdepth:
        payload['sslocspresponder']['batchingdepth'] = True

    if batchingdelay:
        payload['sslocspresponder']['batchingdelay'] = True

    if resptimeout:
        payload['sslocspresponder']['resptimeout'] = True

    if respondercert:
        payload['sslocspresponder']['respondercert'] = True

    if trustresponder:
        payload['sslocspresponder']['trustresponder'] = True

    if producedattimeskew:
        payload['sslocspresponder']['producedattimeskew'] = True

    if signingcert:
        payload['sslocspresponder']['signingcert'] = True

    if usenonce:
        payload['sslocspresponder']['usenonce'] = True

    if insertclientcert:
        payload['sslocspresponder']['insertclientcert'] = True

    execution = __proxy__['citrixns.post']('config/sslocspresponder?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslparameter(quantumsize=None, crlmemorysizemb=None, strictcachecks=None, ssltriggertimeout=None,
                       sendclosenotify=None, encrypttriggerpktcount=None, denysslreneg=None, insertionencoding=None,
                       ocspcachesize=None, pushflag=None, dropreqwithnohostheader=None, pushenctriggertimeout=None,
                       cryptodevdisablelimit=None, undefactioncontrol=None, undefactiondata=None, defaultprofile=None,
                       softwarecryptothreshold=None, hybridfipsmode=None, sigdigesttype=None, sslierrorcache=None,
                       sslimaxerrorcachemem=None, insertcertspace=None, save=False):
    '''
    Unsets values from the sslparameter configuration key.

    quantumsize(bool): Unsets the quantumsize value.

    crlmemorysizemb(bool): Unsets the crlmemorysizemb value.

    strictcachecks(bool): Unsets the strictcachecks value.

    ssltriggertimeout(bool): Unsets the ssltriggertimeout value.

    sendclosenotify(bool): Unsets the sendclosenotify value.

    encrypttriggerpktcount(bool): Unsets the encrypttriggerpktcount value.

    denysslreneg(bool): Unsets the denysslreneg value.

    insertionencoding(bool): Unsets the insertionencoding value.

    ocspcachesize(bool): Unsets the ocspcachesize value.

    pushflag(bool): Unsets the pushflag value.

    dropreqwithnohostheader(bool): Unsets the dropreqwithnohostheader value.

    pushenctriggertimeout(bool): Unsets the pushenctriggertimeout value.

    cryptodevdisablelimit(bool): Unsets the cryptodevdisablelimit value.

    undefactioncontrol(bool): Unsets the undefactioncontrol value.

    undefactiondata(bool): Unsets the undefactiondata value.

    defaultprofile(bool): Unsets the defaultprofile value.

    softwarecryptothreshold(bool): Unsets the softwarecryptothreshold value.

    hybridfipsmode(bool): Unsets the hybridfipsmode value.

    sigdigesttype(bool): Unsets the sigdigesttype value.

    sslierrorcache(bool): Unsets the sslierrorcache value.

    sslimaxerrorcachemem(bool): Unsets the sslimaxerrorcachemem value.

    insertcertspace(bool): Unsets the insertcertspace value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslparameter <args>

    '''

    result = {}

    payload = {'sslparameter': {}}

    if quantumsize:
        payload['sslparameter']['quantumsize'] = True

    if crlmemorysizemb:
        payload['sslparameter']['crlmemorysizemb'] = True

    if strictcachecks:
        payload['sslparameter']['strictcachecks'] = True

    if ssltriggertimeout:
        payload['sslparameter']['ssltriggertimeout'] = True

    if sendclosenotify:
        payload['sslparameter']['sendclosenotify'] = True

    if encrypttriggerpktcount:
        payload['sslparameter']['encrypttriggerpktcount'] = True

    if denysslreneg:
        payload['sslparameter']['denysslreneg'] = True

    if insertionencoding:
        payload['sslparameter']['insertionencoding'] = True

    if ocspcachesize:
        payload['sslparameter']['ocspcachesize'] = True

    if pushflag:
        payload['sslparameter']['pushflag'] = True

    if dropreqwithnohostheader:
        payload['sslparameter']['dropreqwithnohostheader'] = True

    if pushenctriggertimeout:
        payload['sslparameter']['pushenctriggertimeout'] = True

    if cryptodevdisablelimit:
        payload['sslparameter']['cryptodevdisablelimit'] = True

    if undefactioncontrol:
        payload['sslparameter']['undefactioncontrol'] = True

    if undefactiondata:
        payload['sslparameter']['undefactiondata'] = True

    if defaultprofile:
        payload['sslparameter']['defaultprofile'] = True

    if softwarecryptothreshold:
        payload['sslparameter']['softwarecryptothreshold'] = True

    if hybridfipsmode:
        payload['sslparameter']['hybridfipsmode'] = True

    if sigdigesttype:
        payload['sslparameter']['sigdigesttype'] = True

    if sslierrorcache:
        payload['sslparameter']['sslierrorcache'] = True

    if sslimaxerrorcachemem:
        payload['sslparameter']['sslimaxerrorcachemem'] = True

    if insertcertspace:
        payload['sslparameter']['insertcertspace'] = True

    execution = __proxy__['citrixns.post']('config/sslparameter?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslpolicy(name=None, rule=None, reqaction=None, action=None, undefaction=None, comment=None, save=False):
    '''
    Unsets values from the sslpolicy configuration key.

    name(bool): Unsets the name value.

    rule(bool): Unsets the rule value.

    reqaction(bool): Unsets the reqaction value.

    action(bool): Unsets the action value.

    undefaction(bool): Unsets the undefaction value.

    comment(bool): Unsets the comment value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslpolicy <args>

    '''

    result = {}

    payload = {'sslpolicy': {}}

    if name:
        payload['sslpolicy']['name'] = True

    if rule:
        payload['sslpolicy']['rule'] = True

    if reqaction:
        payload['sslpolicy']['reqaction'] = True

    if action:
        payload['sslpolicy']['action'] = True

    if undefaction:
        payload['sslpolicy']['undefaction'] = True

    if comment:
        payload['sslpolicy']['comment'] = True

    execution = __proxy__['citrixns.post']('config/sslpolicy?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslprofile(name=None, sslprofiletype=None, dhcount=None, dh=None, dhfile=None, ersa=None, ersacount=None,
                     sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None, clientauth=None,
                     clientcert=None, dhkeyexpsizelimit=None, sslredirect=None, redirectportrewrite=None, ssl3=None,
                     tls1=None, tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None,
                     commonname=None, pushenctrigger=None, sendclosenotify=None, cleartextport=None,
                     insertionencoding=None, denysslreneg=None, quantumsize=None, strictcachecks=None,
                     encrypttriggerpktcount=None, pushflag=None, dropreqwithnohostheader=None,
                     pushenctriggertimeout=None, ssltriggertimeout=None, clientauthuseboundcachain=None,
                     sessionticket=None, sessionticketlifetime=None, hsts=None, maxage=None, includesubdomains=None,
                     ciphername=None, cipherpriority=None, strictsigdigestcheck=None, save=False):
    '''
    Unsets values from the sslprofile configuration key.

    name(bool): Unsets the name value.

    sslprofiletype(bool): Unsets the sslprofiletype value.

    dhcount(bool): Unsets the dhcount value.

    dh(bool): Unsets the dh value.

    dhfile(bool): Unsets the dhfile value.

    ersa(bool): Unsets the ersa value.

    ersacount(bool): Unsets the ersacount value.

    sessreuse(bool): Unsets the sessreuse value.

    sesstimeout(bool): Unsets the sesstimeout value.

    cipherredirect(bool): Unsets the cipherredirect value.

    cipherurl(bool): Unsets the cipherurl value.

    clientauth(bool): Unsets the clientauth value.

    clientcert(bool): Unsets the clientcert value.

    dhkeyexpsizelimit(bool): Unsets the dhkeyexpsizelimit value.

    sslredirect(bool): Unsets the sslredirect value.

    redirectportrewrite(bool): Unsets the redirectportrewrite value.

    ssl3(bool): Unsets the ssl3 value.

    tls1(bool): Unsets the tls1 value.

    tls11(bool): Unsets the tls11 value.

    tls12(bool): Unsets the tls12 value.

    snienable(bool): Unsets the snienable value.

    ocspstapling(bool): Unsets the ocspstapling value.

    serverauth(bool): Unsets the serverauth value.

    commonname(bool): Unsets the commonname value.

    pushenctrigger(bool): Unsets the pushenctrigger value.

    sendclosenotify(bool): Unsets the sendclosenotify value.

    cleartextport(bool): Unsets the cleartextport value.

    insertionencoding(bool): Unsets the insertionencoding value.

    denysslreneg(bool): Unsets the denysslreneg value.

    quantumsize(bool): Unsets the quantumsize value.

    strictcachecks(bool): Unsets the strictcachecks value.

    encrypttriggerpktcount(bool): Unsets the encrypttriggerpktcount value.

    pushflag(bool): Unsets the pushflag value.

    dropreqwithnohostheader(bool): Unsets the dropreqwithnohostheader value.

    pushenctriggertimeout(bool): Unsets the pushenctriggertimeout value.

    ssltriggertimeout(bool): Unsets the ssltriggertimeout value.

    clientauthuseboundcachain(bool): Unsets the clientauthuseboundcachain value.

    sessionticket(bool): Unsets the sessionticket value.

    sessionticketlifetime(bool): Unsets the sessionticketlifetime value.

    hsts(bool): Unsets the hsts value.

    maxage(bool): Unsets the maxage value.

    includesubdomains(bool): Unsets the includesubdomains value.

    ciphername(bool): Unsets the ciphername value.

    cipherpriority(bool): Unsets the cipherpriority value.

    strictsigdigestcheck(bool): Unsets the strictsigdigestcheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslprofile <args>

    '''

    result = {}

    payload = {'sslprofile': {}}

    if name:
        payload['sslprofile']['name'] = True

    if sslprofiletype:
        payload['sslprofile']['sslprofiletype'] = True

    if dhcount:
        payload['sslprofile']['dhcount'] = True

    if dh:
        payload['sslprofile']['dh'] = True

    if dhfile:
        payload['sslprofile']['dhfile'] = True

    if ersa:
        payload['sslprofile']['ersa'] = True

    if ersacount:
        payload['sslprofile']['ersacount'] = True

    if sessreuse:
        payload['sslprofile']['sessreuse'] = True

    if sesstimeout:
        payload['sslprofile']['sesstimeout'] = True

    if cipherredirect:
        payload['sslprofile']['cipherredirect'] = True

    if cipherurl:
        payload['sslprofile']['cipherurl'] = True

    if clientauth:
        payload['sslprofile']['clientauth'] = True

    if clientcert:
        payload['sslprofile']['clientcert'] = True

    if dhkeyexpsizelimit:
        payload['sslprofile']['dhkeyexpsizelimit'] = True

    if sslredirect:
        payload['sslprofile']['sslredirect'] = True

    if redirectportrewrite:
        payload['sslprofile']['redirectportrewrite'] = True

    if ssl3:
        payload['sslprofile']['ssl3'] = True

    if tls1:
        payload['sslprofile']['tls1'] = True

    if tls11:
        payload['sslprofile']['tls11'] = True

    if tls12:
        payload['sslprofile']['tls12'] = True

    if snienable:
        payload['sslprofile']['snienable'] = True

    if ocspstapling:
        payload['sslprofile']['ocspstapling'] = True

    if serverauth:
        payload['sslprofile']['serverauth'] = True

    if commonname:
        payload['sslprofile']['commonname'] = True

    if pushenctrigger:
        payload['sslprofile']['pushenctrigger'] = True

    if sendclosenotify:
        payload['sslprofile']['sendclosenotify'] = True

    if cleartextport:
        payload['sslprofile']['cleartextport'] = True

    if insertionencoding:
        payload['sslprofile']['insertionencoding'] = True

    if denysslreneg:
        payload['sslprofile']['denysslreneg'] = True

    if quantumsize:
        payload['sslprofile']['quantumsize'] = True

    if strictcachecks:
        payload['sslprofile']['strictcachecks'] = True

    if encrypttriggerpktcount:
        payload['sslprofile']['encrypttriggerpktcount'] = True

    if pushflag:
        payload['sslprofile']['pushflag'] = True

    if dropreqwithnohostheader:
        payload['sslprofile']['dropreqwithnohostheader'] = True

    if pushenctriggertimeout:
        payload['sslprofile']['pushenctriggertimeout'] = True

    if ssltriggertimeout:
        payload['sslprofile']['ssltriggertimeout'] = True

    if clientauthuseboundcachain:
        payload['sslprofile']['clientauthuseboundcachain'] = True

    if sessionticket:
        payload['sslprofile']['sessionticket'] = True

    if sessionticketlifetime:
        payload['sslprofile']['sessionticketlifetime'] = True

    if hsts:
        payload['sslprofile']['hsts'] = True

    if maxage:
        payload['sslprofile']['maxage'] = True

    if includesubdomains:
        payload['sslprofile']['includesubdomains'] = True

    if ciphername:
        payload['sslprofile']['ciphername'] = True

    if cipherpriority:
        payload['sslprofile']['cipherpriority'] = True

    if strictsigdigestcheck:
        payload['sslprofile']['strictsigdigestcheck'] = True

    execution = __proxy__['citrixns.post']('config/sslprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslservice(servicename=None, dh=None, dhfile=None, dhcount=None, dhkeyexpsizelimit=None, ersa=None,
                     ersacount=None, sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None,
                     sslv2redirect=None, sslv2url=None, clientauth=None, clientcert=None, sslredirect=None,
                     redirectportrewrite=None, ssl2=None, ssl3=None, tls1=None, tls11=None, tls12=None, snienable=None,
                     ocspstapling=None, serverauth=None, commonname=None, pushenctrigger=None, sendclosenotify=None,
                     dtlsprofilename=None, sslprofile=None, strictsigdigestcheck=None, save=False):
    '''
    Unsets values from the sslservice configuration key.

    servicename(bool): Unsets the servicename value.

    dh(bool): Unsets the dh value.

    dhfile(bool): Unsets the dhfile value.

    dhcount(bool): Unsets the dhcount value.

    dhkeyexpsizelimit(bool): Unsets the dhkeyexpsizelimit value.

    ersa(bool): Unsets the ersa value.

    ersacount(bool): Unsets the ersacount value.

    sessreuse(bool): Unsets the sessreuse value.

    sesstimeout(bool): Unsets the sesstimeout value.

    cipherredirect(bool): Unsets the cipherredirect value.

    cipherurl(bool): Unsets the cipherurl value.

    sslv2redirect(bool): Unsets the sslv2redirect value.

    sslv2url(bool): Unsets the sslv2url value.

    clientauth(bool): Unsets the clientauth value.

    clientcert(bool): Unsets the clientcert value.

    sslredirect(bool): Unsets the sslredirect value.

    redirectportrewrite(bool): Unsets the redirectportrewrite value.

    ssl2(bool): Unsets the ssl2 value.

    ssl3(bool): Unsets the ssl3 value.

    tls1(bool): Unsets the tls1 value.

    tls11(bool): Unsets the tls11 value.

    tls12(bool): Unsets the tls12 value.

    snienable(bool): Unsets the snienable value.

    ocspstapling(bool): Unsets the ocspstapling value.

    serverauth(bool): Unsets the serverauth value.

    commonname(bool): Unsets the commonname value.

    pushenctrigger(bool): Unsets the pushenctrigger value.

    sendclosenotify(bool): Unsets the sendclosenotify value.

    dtlsprofilename(bool): Unsets the dtlsprofilename value.

    sslprofile(bool): Unsets the sslprofile value.

    strictsigdigestcheck(bool): Unsets the strictsigdigestcheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslservice <args>

    '''

    result = {}

    payload = {'sslservice': {}}

    if servicename:
        payload['sslservice']['servicename'] = True

    if dh:
        payload['sslservice']['dh'] = True

    if dhfile:
        payload['sslservice']['dhfile'] = True

    if dhcount:
        payload['sslservice']['dhcount'] = True

    if dhkeyexpsizelimit:
        payload['sslservice']['dhkeyexpsizelimit'] = True

    if ersa:
        payload['sslservice']['ersa'] = True

    if ersacount:
        payload['sslservice']['ersacount'] = True

    if sessreuse:
        payload['sslservice']['sessreuse'] = True

    if sesstimeout:
        payload['sslservice']['sesstimeout'] = True

    if cipherredirect:
        payload['sslservice']['cipherredirect'] = True

    if cipherurl:
        payload['sslservice']['cipherurl'] = True

    if sslv2redirect:
        payload['sslservice']['sslv2redirect'] = True

    if sslv2url:
        payload['sslservice']['sslv2url'] = True

    if clientauth:
        payload['sslservice']['clientauth'] = True

    if clientcert:
        payload['sslservice']['clientcert'] = True

    if sslredirect:
        payload['sslservice']['sslredirect'] = True

    if redirectportrewrite:
        payload['sslservice']['redirectportrewrite'] = True

    if ssl2:
        payload['sslservice']['ssl2'] = True

    if ssl3:
        payload['sslservice']['ssl3'] = True

    if tls1:
        payload['sslservice']['tls1'] = True

    if tls11:
        payload['sslservice']['tls11'] = True

    if tls12:
        payload['sslservice']['tls12'] = True

    if snienable:
        payload['sslservice']['snienable'] = True

    if ocspstapling:
        payload['sslservice']['ocspstapling'] = True

    if serverauth:
        payload['sslservice']['serverauth'] = True

    if commonname:
        payload['sslservice']['commonname'] = True

    if pushenctrigger:
        payload['sslservice']['pushenctrigger'] = True

    if sendclosenotify:
        payload['sslservice']['sendclosenotify'] = True

    if dtlsprofilename:
        payload['sslservice']['dtlsprofilename'] = True

    if sslprofile:
        payload['sslservice']['sslprofile'] = True

    if strictsigdigestcheck:
        payload['sslservice']['strictsigdigestcheck'] = True

    execution = __proxy__['citrixns.post']('config/sslservice?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslservicegroup(servicegroupname=None, sslprofile=None, sessreuse=None, sesstimeout=None, ssl3=None, tls1=None,
                          tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None, commonname=None,
                          sendclosenotify=None, strictsigdigestcheck=None, save=False):
    '''
    Unsets values from the sslservicegroup configuration key.

    servicegroupname(bool): Unsets the servicegroupname value.

    sslprofile(bool): Unsets the sslprofile value.

    sessreuse(bool): Unsets the sessreuse value.

    sesstimeout(bool): Unsets the sesstimeout value.

    ssl3(bool): Unsets the ssl3 value.

    tls1(bool): Unsets the tls1 value.

    tls11(bool): Unsets the tls11 value.

    tls12(bool): Unsets the tls12 value.

    snienable(bool): Unsets the snienable value.

    ocspstapling(bool): Unsets the ocspstapling value.

    serverauth(bool): Unsets the serverauth value.

    commonname(bool): Unsets the commonname value.

    sendclosenotify(bool): Unsets the sendclosenotify value.

    strictsigdigestcheck(bool): Unsets the strictsigdigestcheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslservicegroup <args>

    '''

    result = {}

    payload = {'sslservicegroup': {}}

    if servicegroupname:
        payload['sslservicegroup']['servicegroupname'] = True

    if sslprofile:
        payload['sslservicegroup']['sslprofile'] = True

    if sessreuse:
        payload['sslservicegroup']['sessreuse'] = True

    if sesstimeout:
        payload['sslservicegroup']['sesstimeout'] = True

    if ssl3:
        payload['sslservicegroup']['ssl3'] = True

    if tls1:
        payload['sslservicegroup']['tls1'] = True

    if tls11:
        payload['sslservicegroup']['tls11'] = True

    if tls12:
        payload['sslservicegroup']['tls12'] = True

    if snienable:
        payload['sslservicegroup']['snienable'] = True

    if ocspstapling:
        payload['sslservicegroup']['ocspstapling'] = True

    if serverauth:
        payload['sslservicegroup']['serverauth'] = True

    if commonname:
        payload['sslservicegroup']['commonname'] = True

    if sendclosenotify:
        payload['sslservicegroup']['sendclosenotify'] = True

    if strictsigdigestcheck:
        payload['sslservicegroup']['strictsigdigestcheck'] = True

    execution = __proxy__['citrixns.post']('config/sslservicegroup?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_sslvserver(vservername=None, cleartextport=None, dh=None, dhfile=None, dhcount=None, dhkeyexpsizelimit=None,
                     ersa=None, ersacount=None, sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None,
                     sslv2redirect=None, sslv2url=None, clientauth=None, clientcert=None, sslredirect=None,
                     redirectportrewrite=None, ssl2=None, ssl3=None, tls1=None, tls11=None, tls12=None, snienable=None,
                     ocspstapling=None, pushenctrigger=None, sendclosenotify=None, dtlsprofilename=None, sslprofile=None,
                     hsts=None, maxage=None, includesubdomains=None, strictsigdigestcheck=None, save=False):
    '''
    Unsets values from the sslvserver configuration key.

    vservername(bool): Unsets the vservername value.

    cleartextport(bool): Unsets the cleartextport value.

    dh(bool): Unsets the dh value.

    dhfile(bool): Unsets the dhfile value.

    dhcount(bool): Unsets the dhcount value.

    dhkeyexpsizelimit(bool): Unsets the dhkeyexpsizelimit value.

    ersa(bool): Unsets the ersa value.

    ersacount(bool): Unsets the ersacount value.

    sessreuse(bool): Unsets the sessreuse value.

    sesstimeout(bool): Unsets the sesstimeout value.

    cipherredirect(bool): Unsets the cipherredirect value.

    cipherurl(bool): Unsets the cipherurl value.

    sslv2redirect(bool): Unsets the sslv2redirect value.

    sslv2url(bool): Unsets the sslv2url value.

    clientauth(bool): Unsets the clientauth value.

    clientcert(bool): Unsets the clientcert value.

    sslredirect(bool): Unsets the sslredirect value.

    redirectportrewrite(bool): Unsets the redirectportrewrite value.

    ssl2(bool): Unsets the ssl2 value.

    ssl3(bool): Unsets the ssl3 value.

    tls1(bool): Unsets the tls1 value.

    tls11(bool): Unsets the tls11 value.

    tls12(bool): Unsets the tls12 value.

    snienable(bool): Unsets the snienable value.

    ocspstapling(bool): Unsets the ocspstapling value.

    pushenctrigger(bool): Unsets the pushenctrigger value.

    sendclosenotify(bool): Unsets the sendclosenotify value.

    dtlsprofilename(bool): Unsets the dtlsprofilename value.

    sslprofile(bool): Unsets the sslprofile value.

    hsts(bool): Unsets the hsts value.

    maxage(bool): Unsets the maxage value.

    includesubdomains(bool): Unsets the includesubdomains value.

    strictsigdigestcheck(bool): Unsets the strictsigdigestcheck value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.unset_sslvserver <args>

    '''

    result = {}

    payload = {'sslvserver': {}}

    if vservername:
        payload['sslvserver']['vservername'] = True

    if cleartextport:
        payload['sslvserver']['cleartextport'] = True

    if dh:
        payload['sslvserver']['dh'] = True

    if dhfile:
        payload['sslvserver']['dhfile'] = True

    if dhcount:
        payload['sslvserver']['dhcount'] = True

    if dhkeyexpsizelimit:
        payload['sslvserver']['dhkeyexpsizelimit'] = True

    if ersa:
        payload['sslvserver']['ersa'] = True

    if ersacount:
        payload['sslvserver']['ersacount'] = True

    if sessreuse:
        payload['sslvserver']['sessreuse'] = True

    if sesstimeout:
        payload['sslvserver']['sesstimeout'] = True

    if cipherredirect:
        payload['sslvserver']['cipherredirect'] = True

    if cipherurl:
        payload['sslvserver']['cipherurl'] = True

    if sslv2redirect:
        payload['sslvserver']['sslv2redirect'] = True

    if sslv2url:
        payload['sslvserver']['sslv2url'] = True

    if clientauth:
        payload['sslvserver']['clientauth'] = True

    if clientcert:
        payload['sslvserver']['clientcert'] = True

    if sslredirect:
        payload['sslvserver']['sslredirect'] = True

    if redirectportrewrite:
        payload['sslvserver']['redirectportrewrite'] = True

    if ssl2:
        payload['sslvserver']['ssl2'] = True

    if ssl3:
        payload['sslvserver']['ssl3'] = True

    if tls1:
        payload['sslvserver']['tls1'] = True

    if tls11:
        payload['sslvserver']['tls11'] = True

    if tls12:
        payload['sslvserver']['tls12'] = True

    if snienable:
        payload['sslvserver']['snienable'] = True

    if ocspstapling:
        payload['sslvserver']['ocspstapling'] = True

    if pushenctrigger:
        payload['sslvserver']['pushenctrigger'] = True

    if sendclosenotify:
        payload['sslvserver']['sendclosenotify'] = True

    if dtlsprofilename:
        payload['sslvserver']['dtlsprofilename'] = True

    if sslprofile:
        payload['sslvserver']['sslprofile'] = True

    if hsts:
        payload['sslvserver']['hsts'] = True

    if maxage:
        payload['sslvserver']['maxage'] = True

    if includesubdomains:
        payload['sslvserver']['includesubdomains'] = True

    if strictsigdigestcheck:
        payload['sslvserver']['strictsigdigestcheck'] = True

    execution = __proxy__['citrixns.post']('config/sslvserver?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslcertkey(certkey=None, cert=None, key=None, password=None, fipskey=None, hsmkey=None, inform=None,
                      passplain=None, expirymonitor=None, notificationperiod=None, bundle=None, linkcertkeyname=None,
                      nodomaincheck=None, save=False):
    '''
    Update the running configuration for the sslcertkey config key.

    certkey(str): Name for the certificate and private-key pair. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the certificate-key pair is created.  The
        following requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the
        name in double or single quotation marks (for example, "my cert" or my cert). Minimum length = 1

    cert(str): Name of and, optionally, path to the X509 certificate file that is used to form the certificate-key pair. The
        certificate file should be present on the appliances hard-disk drive or solid-state drive. Storing a certificate
        in any location other than the default might cause inconsistency in a high availability setup. /nsconfig/ssl/ is
        the default path. Minimum length = 1

    key(str): Name of and, optionally, path to the private-key file that is used to form the certificate-key pair. The
        certificate file should be present on the appliances hard-disk drive or solid-state drive. Storing a certificate
        in any location other than the default might cause inconsistency in a high availability setup. /nsconfig/ssl/ is
        the default path. Minimum length = 1

    password(bool): Passphrase that was used to encrypt the private-key. Use this option to load encrypted private-keys in
        PEM format.

    fipskey(str): Name of the FIPS key that was created inside the Hardware Security Module (HSM) of a FIPS appliance, or a
        key that was imported into the HSM. Minimum length = 1

    hsmkey(str): Name of the HSM key that was created in the External Hardware Security Module (HSM) of a FIPS appliance.
        Minimum length = 1

    inform(str): Input format of the certificate and the private-key files. The three formats supported by the appliance are:
        PEM - Privacy Enhanced Mail DER - Distinguished Encoding Rule PFX - Personal Information Exchange. Default value:
        PEM Possible values = DER, PEM, PFX

    passplain(str): Pass phrase used to encrypt the private-key. Required when adding an encrypted private-key in PEM format.
        Minimum length = 1

    expirymonitor(str): Issue an alert when the certificate is about to expire. Possible values = ENABLED, DISABLED

    notificationperiod(int): Time, in number of days, before certificate expiration, at which to generate an alert that the
        certificate is about to expire. Minimum value = 10 Maximum value = 100

    bundle(str): Parse the certificate chain as a single file after linking the server certificate to its issuers certificate
        within the file. Default value: NO Possible values = YES, NO

    linkcertkeyname(str): Name of the Certificate Authority certificate-key pair to which to link a certificate-key pair.
        Minimum length = 1

    nodomaincheck(bool): Override the check for matching domain names during a certificate update operation.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslcertkey <args>

    '''

    result = {}

    payload = {'sslcertkey': {}}

    if certkey:
        payload['sslcertkey']['certkey'] = certkey

    if cert:
        payload['sslcertkey']['cert'] = cert

    if key:
        payload['sslcertkey']['key'] = key

    if password:
        payload['sslcertkey']['password'] = password

    if fipskey:
        payload['sslcertkey']['fipskey'] = fipskey

    if hsmkey:
        payload['sslcertkey']['hsmkey'] = hsmkey

    if inform:
        payload['sslcertkey']['inform'] = inform

    if passplain:
        payload['sslcertkey']['passplain'] = passplain

    if expirymonitor:
        payload['sslcertkey']['expirymonitor'] = expirymonitor

    if notificationperiod:
        payload['sslcertkey']['notificationperiod'] = notificationperiod

    if bundle:
        payload['sslcertkey']['bundle'] = bundle

    if linkcertkeyname:
        payload['sslcertkey']['linkcertkeyname'] = linkcertkeyname

    if nodomaincheck:
        payload['sslcertkey']['nodomaincheck'] = nodomaincheck

    execution = __proxy__['citrixns.put']('config/sslcertkey', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslcipher(ciphergroupname=None, ciphgrpalias=None, ciphername=None, cipherpriority=None, sslprofile=None,
                     save=False):
    '''
    Update the running configuration for the sslcipher config key.

    ciphergroupname(str): Name for the user-defined cipher group. Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the cipher group is created.  The following
        requirement applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in
        double or single quotation marks (for example, "my ciphergroup" or my ciphergroup). Minimum length = 1

    ciphgrpalias(str): The individual cipher name(s), a user-defined cipher group, or a system predefined cipher alias that
        will be added to the predefined cipher alias that will be added to the group cipherGroupName. If a cipher alias
        or a cipher group is specified, all the individual ciphers in the cipher alias or group will be added to the
        user-defined cipher group. Minimum length = 1

    ciphername(str): Cipher name.

    cipherpriority(int): This indicates priority assigned to the particular cipher. Minimum value = 1

    sslprofile(str): Name of the profile to which cipher is attached.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslcipher <args>

    '''

    result = {}

    payload = {'sslcipher': {}}

    if ciphergroupname:
        payload['sslcipher']['ciphergroupname'] = ciphergroupname

    if ciphgrpalias:
        payload['sslcipher']['ciphgrpalias'] = ciphgrpalias

    if ciphername:
        payload['sslcipher']['ciphername'] = ciphername

    if cipherpriority:
        payload['sslcipher']['cipherpriority'] = cipherpriority

    if sslprofile:
        payload['sslcipher']['sslprofile'] = sslprofile

    execution = __proxy__['citrixns.put']('config/sslcipher', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslcrl(crlname=None, crlpath=None, inform=None, refresh=None, cacert=None, method=None, server=None, url=None,
                  port=None, basedn=None, scope=None, interval=None, day=None, time=None, binddn=None, password=None,
                  binary=None, cacertfile=None, cakeyfile=None, indexfile=None, revoke=None, gencrl=None, save=False):
    '''
    Update the running configuration for the sslcrl config key.

    crlname(str): Name for the Certificate Revocation List (CRL). Must begin with an ASCII alphanumeric or underscore (_)
        character, and must contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),
        equals (=), and hyphen (-) characters. Cannot be changed after the CRL is created.  The following requirement
        applies only to the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single
        quotation marks (for example, "my crl" or my crl). Minimum length = 1

    crlpath(str): Path to the CRL file. /var/netscaler/ssl/ is the default path. Minimum length = 1

    inform(str): Input format of the CRL file. The two formats supported on the appliance are: PEM - Privacy Enhanced Mail.
        DER - Distinguished Encoding Rule. Default value: PEM Possible values = DER, PEM

    refresh(str): Set CRL auto refresh. Possible values = ENABLED, DISABLED

    cacert(str): CA certificate that has issued the CRL. Required if CRL Auto Refresh is selected. Install the CA certificate
        on the appliance before adding the CRL. Minimum length = 1

    method(str): Method for CRL refresh. If LDAP is selected, specify the method, CA certificate, base DN, port, and LDAP
        server name. If HTTP is selected, specify the CA certificate, method, URL, and port. Cannot be changed after a
        CRL is added. Possible values = HTTP, LDAP

    server(str): IP address of the LDAP server from which to fetch the CRLs. Minimum length = 1

    url(str): URL of the CRL distribution point.

    port(int): Port for the LDAP server. Minimum value = 1

    basedn(str): Base distinguished name (DN), which is used in an LDAP search to search for a CRL. Citrix recommends
        searching for the Base DN instead of the Issuer Name from the CA certificate, because the Issuer Name field might
        not exactly match the LDAP directory structures DN. Minimum length = 1

    scope(str): Extent of the search operation on the LDAP server. Available settings function as follows: One - One level
        below Base DN. Base - Exactly the same level as Base DN. Default value: One Possible values = Base, One

    interval(str): CRL refresh interval. Use the NONE setting to unset this parameter. Possible values = MONTHLY, WEEKLY,
        DAILY, NONE

    day(int): Day on which to refresh the CRL, or, if the Interval parameter is not set, the number of days after which to
        refresh the CRL. If Interval is set to MONTHLY, specify the date. If Interval is set to WEEKLY, specify the day
        of the week (for example, Sun=0 and Sat=6). This parameter is not applicable if the Interval is set to DAILY.
        Minimum value = 0 Maximum value = 31

    time(str): Time, in hours (1-24) and minutes (1-60), at which to refresh the CRL.

    binddn(str): Bind distinguished name (DN) to be used to access the CRL object in the LDAP repository if access to the
        LDAP repository is restricted or anonymous access is not allowed. Minimum length = 1

    password(str): Password to access the CRL in the LDAP repository if access to the LDAP repository is restricted or
        anonymous access is not allowed. Minimum length = 1

    binary(str): Set the LDAP-based CRL retrieval mode to binary. Default value: NO Possible values = YES, NO

    cacertfile(str): Name of and, optionally, path to the CA certificate file. /nsconfig/ssl/ is the default path. Maximum
        length = 63

    cakeyfile(str): Name of and, optionally, path to the CA key file. /nsconfig/ssl/ is the default path. Maximum length =
        63

    indexfile(str): Name of and, optionally, path to the file containing the serial numbers of all the certificates that are
        revoked. Revoked certificates are appended to the file. /nsconfig/ssl/ is the default path. Maximum length = 63

    revoke(str): Name of and, optionally, path to the certificate to be revoked. /nsconfig/ssl/ is the default path. Maximum
        length = 63

    gencrl(str): Name of and, optionally, path to the CRL file to be generated. The list of certificates that have been
        revoked is obtained from the index file. /nsconfig/ssl/ is the default path. Maximum length = 63

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslcrl <args>

    '''

    result = {}

    payload = {'sslcrl': {}}

    if crlname:
        payload['sslcrl']['crlname'] = crlname

    if crlpath:
        payload['sslcrl']['crlpath'] = crlpath

    if inform:
        payload['sslcrl']['inform'] = inform

    if refresh:
        payload['sslcrl']['refresh'] = refresh

    if cacert:
        payload['sslcrl']['cacert'] = cacert

    if method:
        payload['sslcrl']['method'] = method

    if server:
        payload['sslcrl']['server'] = server

    if url:
        payload['sslcrl']['url'] = url

    if port:
        payload['sslcrl']['port'] = port

    if basedn:
        payload['sslcrl']['basedn'] = basedn

    if scope:
        payload['sslcrl']['scope'] = scope

    if interval:
        payload['sslcrl']['interval'] = interval

    if day:
        payload['sslcrl']['day'] = day

    if time:
        payload['sslcrl']['time'] = time

    if binddn:
        payload['sslcrl']['binddn'] = binddn

    if password:
        payload['sslcrl']['password'] = password

    if binary:
        payload['sslcrl']['binary'] = binary

    if cacertfile:
        payload['sslcrl']['cacertfile'] = cacertfile

    if cakeyfile:
        payload['sslcrl']['cakeyfile'] = cakeyfile

    if indexfile:
        payload['sslcrl']['indexfile'] = indexfile

    if revoke:
        payload['sslcrl']['revoke'] = revoke

    if gencrl:
        payload['sslcrl']['gencrl'] = gencrl

    execution = __proxy__['citrixns.put']('config/sslcrl', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_ssldtlsprofile(name=None, pmtudiscovery=None, maxrecordsize=None, maxretrytime=None, helloverifyrequest=None,
                          terminatesession=None, maxpacketsize=None, save=False):
    '''
    Update the running configuration for the ssldtlsprofile config key.

    name(str): Name for the DTLS profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@),equals sign (=), and hyphen
        (-) characters. Cannot be changed after the profile is created. Minimum length = 1 Maximum length = 127

    pmtudiscovery(str): Source for the maximum record size value. If ENABLED, the value is taken from the PMTU table. If
        DISABLED, the value is taken from the profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    maxrecordsize(int): Maximum size of records that can be sent if PMTU is disabled. Default value: 1459 Minimum value = 250
        Maximum value = 1459

    maxretrytime(int): Wait for the specified time, in seconds, before resending the request. Default value: 3

    helloverifyrequest(str): Send a Hello Verify request to validate the client. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    terminatesession(str): Terminate the session if the message authentication code (MAC) of the client and server do not
        match. Default value: DISABLED Possible values = ENABLED, DISABLED

    maxpacketsize(int): Maximum number of packets to reassemble. This value helps protect against a fragmented packet attack.
        Default value: 120 Minimum value = 0 Maximum value = 86400

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_ssldtlsprofile <args>

    '''

    result = {}

    payload = {'ssldtlsprofile': {}}

    if name:
        payload['ssldtlsprofile']['name'] = name

    if pmtudiscovery:
        payload['ssldtlsprofile']['pmtudiscovery'] = pmtudiscovery

    if maxrecordsize:
        payload['ssldtlsprofile']['maxrecordsize'] = maxrecordsize

    if maxretrytime:
        payload['ssldtlsprofile']['maxretrytime'] = maxretrytime

    if helloverifyrequest:
        payload['ssldtlsprofile']['helloverifyrequest'] = helloverifyrequest

    if terminatesession:
        payload['ssldtlsprofile']['terminatesession'] = terminatesession

    if maxpacketsize:
        payload['ssldtlsprofile']['maxpacketsize'] = maxpacketsize

    execution = __proxy__['citrixns.put']('config/ssldtlsprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslfips(inithsm=None, sopassword=None, oldsopassword=None, userpassword=None, hsmlabel=None, fipsfw=None,
                   save=False):
    '''
    Update the running configuration for the sslfips config key.

    inithsm(str): FIPS initialization level. The appliance currently supports Level-2 (FIPS 140-2). Possible values =
        Level-2

    sopassword(str): Security officer password that will be in effect after you have configured the HSM. Minimum length = 1

    oldsopassword(str): Old password for the security officer. Minimum length = 1

    userpassword(str): The Hardware Security Modules (HSM) User password. Minimum length = 1

    hsmlabel(str): Label to identify the Hardware Security Module (HSM). Minimum length = 1

    fipsfw(str): Path to the FIPS firmware file. Minimum length = 1

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslfips <args>

    '''

    result = {}

    payload = {'sslfips': {}}

    if inithsm:
        payload['sslfips']['inithsm'] = inithsm

    if sopassword:
        payload['sslfips']['sopassword'] = sopassword

    if oldsopassword:
        payload['sslfips']['oldsopassword'] = oldsopassword

    if userpassword:
        payload['sslfips']['userpassword'] = userpassword

    if hsmlabel:
        payload['sslfips']['hsmlabel'] = hsmlabel

    if fipsfw:
        payload['sslfips']['fipsfw'] = fipsfw

    execution = __proxy__['citrixns.put']('config/sslfips', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslocspresponder(name=None, url=None, cache=None, cachetimeout=None, batchingdepth=None, batchingdelay=None,
                            resptimeout=None, respondercert=None, trustresponder=None, producedattimeskew=None,
                            signingcert=None, usenonce=None, insertclientcert=None, save=False):
    '''
    Update the running configuration for the sslocspresponder config key.

    name(str): Name for the OCSP responder. Cannot begin with a hash (#) or space character and must contain only ASCII
        alphanumeric, underscore (_), hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the responder is created.  The following requirement applies only to the
        NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks (for
        example, "my responder" or my responder). Minimum length = 1

    url(str): URL of the OCSP responder. Minimum length = 1

    cache(str): Enable caching of responses. Caching of responses received from the OCSP responder enables faster responses
        to the clients and reduces the load on the OCSP responder. Possible values = ENABLED, DISABLED

    cachetimeout(int): Timeout for caching the OCSP response. After the timeout, the NetScaler sends a fresh request to the
        OCSP responder for the certificate status. If a timeout is not specified, the timeout provided in the OCSP
        response applies. Default value: 1 Minimum value = 1 Maximum value = 1440

    batchingdepth(int): Number of client certificates to batch together into one OCSP request. Batching avoids overloading
        the OCSP responder. A value of 1 signifies that each request is queried independently. For a value greater than
        1, specify a timeout (batching delay) to avoid inordinately delaying the processing of a single certificate.
        Minimum value = 1 Maximum value = 8

    batchingdelay(int): Maximum time, in milliseconds, to wait to accumulate OCSP requests to batch. Does not apply if the
        Batching Depth is 1. Minimum value = 0 Maximum value = 10000

    resptimeout(int): Time, in milliseconds, to wait for an OCSP response. When this time elapses, an error message appears
        or the transaction is forwarded, depending on the settings on the virtual server. Includes Batching Delay time.
        Minimum value = 0 Maximum value = 120000

    respondercert(str): . Minimum length = 1

    trustresponder(bool): A certificate to use to validate OCSP responses. Alternatively, if -trustResponder is specified, no
        verification will be done on the reponse. If both are omitted, only the response times (producedAt, lastUpdate,
        nextUpdate) will be verified.

    producedattimeskew(int): Time, in seconds, for which the NetScaler waits before considering the response as invalid. The
        response is considered invalid if the Produced At time stamp in the OCSP response exceeds or precedes the current
        NetScaler clock time by the amount of time specified. Default value: 300 Minimum value = 0 Maximum value = 86400

    signingcert(str): Certificate-key pair that is used to sign OCSP requests. If this parameter is not set, the requests are
        not signed. Minimum length = 1

    usenonce(str): Enable the OCSP nonce extension, which is designed to prevent replay attacks. Possible values = YES, NO

    insertclientcert(str): Include the complete client certificate in the OCSP request. Possible values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslocspresponder <args>

    '''

    result = {}

    payload = {'sslocspresponder': {}}

    if name:
        payload['sslocspresponder']['name'] = name

    if url:
        payload['sslocspresponder']['url'] = url

    if cache:
        payload['sslocspresponder']['cache'] = cache

    if cachetimeout:
        payload['sslocspresponder']['cachetimeout'] = cachetimeout

    if batchingdepth:
        payload['sslocspresponder']['batchingdepth'] = batchingdepth

    if batchingdelay:
        payload['sslocspresponder']['batchingdelay'] = batchingdelay

    if resptimeout:
        payload['sslocspresponder']['resptimeout'] = resptimeout

    if respondercert:
        payload['sslocspresponder']['respondercert'] = respondercert

    if trustresponder:
        payload['sslocspresponder']['trustresponder'] = trustresponder

    if producedattimeskew:
        payload['sslocspresponder']['producedattimeskew'] = producedattimeskew

    if signingcert:
        payload['sslocspresponder']['signingcert'] = signingcert

    if usenonce:
        payload['sslocspresponder']['usenonce'] = usenonce

    if insertclientcert:
        payload['sslocspresponder']['insertclientcert'] = insertclientcert

    execution = __proxy__['citrixns.put']('config/sslocspresponder', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslparameter(quantumsize=None, crlmemorysizemb=None, strictcachecks=None, ssltriggertimeout=None,
                        sendclosenotify=None, encrypttriggerpktcount=None, denysslreneg=None, insertionencoding=None,
                        ocspcachesize=None, pushflag=None, dropreqwithnohostheader=None, pushenctriggertimeout=None,
                        cryptodevdisablelimit=None, undefactioncontrol=None, undefactiondata=None, defaultprofile=None,
                        softwarecryptothreshold=None, hybridfipsmode=None, sigdigesttype=None, sslierrorcache=None,
                        sslimaxerrorcachemem=None, insertcertspace=None, save=False):
    '''
    Update the running configuration for the sslparameter config key.

    quantumsize(str): Amount of data to collect before the data is pushed to the crypto hardware for encryption. For large
        downloads, a larger quantum size better utilizes the crypto resources. Default value: 8192 Possible values =
        4096, 8192, 16384

    crlmemorysizemb(int): Maximum memory size to use for certificate revocation lists (CRLs). This parameter reserves memory
        for a CRL but sets a limit to the maximum memory that the CRLs loaded on the appliance can consume. Default
        value: 256 Minimum value = 10 Maximum value = 1024

    strictcachecks(str): Enable strict CA certificate checks on the appliance. Default value: NO Possible values = YES, NO

    ssltriggertimeout(int): Time, in milliseconds, after which encryption is triggered for transactions that are not tracked
        on the NetScaler appliance because their length is not known. There can be a delay of up to 10ms from the
        specified timeout value before the packet is pushed into the queue. Default value: 100 Minimum value = 1 Maximum
        value = 200

    sendclosenotify(str): Send an SSL Close-Notify message to the client at the end of a transaction. Default value: YES
        Possible values = YES, NO

    encrypttriggerpktcount(int): Maximum number of queued packets after which encryption is triggered. Use this setting for
        SSL transactions that send small packets from server to NetScaler. Default value: 45 Minimum value = 10 Maximum
        value = 50

    denysslreneg(str): Deny renegotiation in specified circumstances. Available settings function as follows: * NO - Allow
        SSL renegotiation. * FRONTEND_CLIENT - Deny secure and nonsecure SSL renegotiation initiated by the client. *
        FRONTEND_CLIENTSERVER - Deny secure and nonsecure SSL renegotiation initiated by the client or the NetScaler
        during policy-based client authentication.  * ALL - Deny all secure and nonsecure SSL renegotiation. * NONSECURE
        - Deny nonsecure SSL renegotiation. Allows only clients that support RFC 5746. Default value: ALL Possible values
        = NO, FRONTEND_CLIENT, FRONTEND_CLIENTSERVER, ALL, NONSECURE

    insertionencoding(str): Encoding method used to insert the subject or issuers name in HTTP requests to servers. Default
        value: Unicode Possible values = Unicode, UTF-8

    ocspcachesize(int): Size, per packet engine, in megabytes, of the OCSP cache. A maximum of 10% of the packet engine
        memory can be assigned. Because the maximum allowed packet engine memory is 4GB, the maximum value that can be
        assigned to the OCSP cache is approximately 410 MB. Default value: 10 Minimum value = 0 Maximum value = 512

    pushflag(int): Insert PUSH flag into decrypted, encrypted, or all records. If the PUSH flag is set to a value other than
        0, the buffered records are forwarded on the basis of the value of the PUSH flag. Available settings function as
        follows: 0 - Auto (PUSH flag is not set.) 1 - Insert PUSH flag into every decrypted record. 2 -Insert PUSH flag
        into every encrypted record. 3 - Insert PUSH flag into every decrypted and encrypted record. Minimum value = 0
        Maximum value = 3

    dropreqwithnohostheader(str): Host header check for SNI enabled sessions. If this check is enabled and the HTTP request
        does not contain the host header for SNI enabled sessions, the request is dropped. Default value: NO Possible
        values = YES, NO

    pushenctriggertimeout(int): PUSH encryption trigger timeout value. The timeout value is applied only if you set the Push
        Encryption Trigger parameter to Timer in the SSL virtual server settings. Default value: 1 Minimum value = 1
        Maximum value = 200

    cryptodevdisablelimit(int): Limit to the number of disabled SSL chips after which the ADC restarts. A value of zero
        implies that the ADC does not automatically restart. Default value: 0

    undefactioncontrol(str): Name of the undefined built-in control action: CLIENTAUTH, NOCLIENTAUTH, NOOP, RESET, or DROP.
        Default value: "CLIENTAUTH"

    undefactiondata(str): Name of the undefined built-in data action: NOOP, RESET or DROP. Default value: "NOOP"

    defaultprofile(str): Global parameter used to enable default profile feature. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    softwarecryptothreshold(int): Netscaler CPU utilization threshold (in percentage) beyond which crypto operations are not
        done in software. A value of zero implies that CPU is not utilized for doing crypto in software. Default value: 0
        Minimum value = 0 Maximum value = 100

    hybridfipsmode(str): When this mode is enabled, system will use additional crypto hardware to accelerate symmetric crypto
        operations. Default value: DISABLED Possible values = ENABLED, DISABLED

    sigdigesttype(list(str)): Signature Digest Algorithms that are supported by appliance. Default value is "ALL" and it will
        enable the following algorithms depending on the platform. On VPX: RSA-MD5 RSA-SHA1 RSA-SHA224 RSA-SHA256
        RSA-SHA384 RSA-SHA512 DSA-SHA1 DSA-SHA224 DSA-SHA256 DSA-SHA384 DSA-SHA512 On MPX with Nitrox-III Cards: RSA-MD5
        RSA-SHA1 RSA-SHA224 RSA-SHA256 RSA-SHA384 RSA-SHA512 ECDSA-SHA1 ECDSA-SHA224 ECDSA-SHA256 ECDSA-SHA384
        ECDSA-SHA512 Others: RSA-MD5 RSA-SHA1 RSA-SHA224 RSA-SHA256 RSA-SHA384 RSA-SHA512.  Default value: ALL Possible
        values = ALL, RSA-MD5, RSA-SHA1, RSA-SHA224, RSA-SHA256, RSA-SHA384, RSA-SHA512, DSA-SHA1, DSA-SHA224,
        DSA-SHA256, DSA-SHA384, DSA-SHA512, ECDSA-SHA1, ECDSA-SHA224, ECDSA-SHA256, ECDSA-SHA384, ECDSA-SHA512

    sslierrorcache(str): Enable or disable dynamically learning and caching the learned information to make the subsequent
        interception or bypass decision. When enabled, NS does the lookup of this cached data to do early bypass. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    sslimaxerrorcachemem(int): Specify the maximum memory that can be used for caching the learned data. This memory is used
        as a LRU cache so that the old entries gets replaced with new entry once the set memory limit is fully utilised.
        A value of 0 decides the limit automatically. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    insertcertspace(str): To insert space between lines in the certificate header of request. Default value: YES Possible
        values = YES, NO

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslparameter <args>

    '''

    result = {}

    payload = {'sslparameter': {}}

    if quantumsize:
        payload['sslparameter']['quantumsize'] = quantumsize

    if crlmemorysizemb:
        payload['sslparameter']['crlmemorysizemb'] = crlmemorysizemb

    if strictcachecks:
        payload['sslparameter']['strictcachecks'] = strictcachecks

    if ssltriggertimeout:
        payload['sslparameter']['ssltriggertimeout'] = ssltriggertimeout

    if sendclosenotify:
        payload['sslparameter']['sendclosenotify'] = sendclosenotify

    if encrypttriggerpktcount:
        payload['sslparameter']['encrypttriggerpktcount'] = encrypttriggerpktcount

    if denysslreneg:
        payload['sslparameter']['denysslreneg'] = denysslreneg

    if insertionencoding:
        payload['sslparameter']['insertionencoding'] = insertionencoding

    if ocspcachesize:
        payload['sslparameter']['ocspcachesize'] = ocspcachesize

    if pushflag:
        payload['sslparameter']['pushflag'] = pushflag

    if dropreqwithnohostheader:
        payload['sslparameter']['dropreqwithnohostheader'] = dropreqwithnohostheader

    if pushenctriggertimeout:
        payload['sslparameter']['pushenctriggertimeout'] = pushenctriggertimeout

    if cryptodevdisablelimit:
        payload['sslparameter']['cryptodevdisablelimit'] = cryptodevdisablelimit

    if undefactioncontrol:
        payload['sslparameter']['undefactioncontrol'] = undefactioncontrol

    if undefactiondata:
        payload['sslparameter']['undefactiondata'] = undefactiondata

    if defaultprofile:
        payload['sslparameter']['defaultprofile'] = defaultprofile

    if softwarecryptothreshold:
        payload['sslparameter']['softwarecryptothreshold'] = softwarecryptothreshold

    if hybridfipsmode:
        payload['sslparameter']['hybridfipsmode'] = hybridfipsmode

    if sigdigesttype:
        payload['sslparameter']['sigdigesttype'] = sigdigesttype

    if sslierrorcache:
        payload['sslparameter']['sslierrorcache'] = sslierrorcache

    if sslimaxerrorcachemem:
        payload['sslparameter']['sslimaxerrorcachemem'] = sslimaxerrorcachemem

    if insertcertspace:
        payload['sslparameter']['insertcertspace'] = insertcertspace

    execution = __proxy__['citrixns.put']('config/sslparameter', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslpolicy(name=None, rule=None, reqaction=None, action=None, undefaction=None, comment=None, save=False):
    '''
    Update the running configuration for the sslpolicy config key.

    name(str): Name for the new SSL policy. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and
        hyphen (-) characters. Cannot be changed after the policy is created.  The following requirement applies only to
        the NetScaler CLI: If the name includes one or more spaces, enclose the name in double or single quotation marks
        (for example, "my policy" or my policy). Minimum length = 1

    rule(str): Expression, against which traffic is evaluated. Written in the classic or default syntax. Note: Maximum length
        of a string literal in the expression is 255 characters. A longer string can be split into smaller strings of up
        to 255 characters each, and the smaller strings concatenated with the + operator. For example, you can create a
        500-character string as follows: ";lt;string of 255 characters;gt;" + ";lt;string of 245 characters;gt;" (Classic
        expressions are not supported in the cluster build.)  The following requirements apply only to the NetScaler CLI:
        * If the expression includes one or more spaces, enclose the entire expression in double quotation marks. * If
        the expression itself includes double quotation marks, escape the quotations by using the character.  *
        Alternatively, you can use single quotation marks to enclose the rule, in which case you do not have to escape
        the double quotation marks.

    reqaction(str): The name of the action to be performed on the request. Refer to add ssl action command to add a new
        action. Builtin actions like NOOP, RESET, DROP, CLIENTAUTH and NOCLIENTAUTH are also allowed. Minimum length = 1

    action(str): Name of the built-in or user-defined action to perform on the request. Available built-in actions are NOOP,
        RESET, DROP, CLIENTAUTH and NOCLIENTAUTH.

    undefaction(str): Name of the action to be performed when the result of rule evaluation is undefined. Possible values for
        control policies: CLIENTAUTH, NOCLIENTAUTH, NOOP, RESET, DROP. Possible values for data policies: NOOP, RESET,
        DROP.

    comment(str): Any comments associated with this policy.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslpolicy <args>

    '''

    result = {}

    payload = {'sslpolicy': {}}

    if name:
        payload['sslpolicy']['name'] = name

    if rule:
        payload['sslpolicy']['rule'] = rule

    if reqaction:
        payload['sslpolicy']['reqaction'] = reqaction

    if action:
        payload['sslpolicy']['action'] = action

    if undefaction:
        payload['sslpolicy']['undefaction'] = undefaction

    if comment:
        payload['sslpolicy']['comment'] = comment

    execution = __proxy__['citrixns.put']('config/sslpolicy', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslprofile(name=None, sslprofiletype=None, dhcount=None, dh=None, dhfile=None, ersa=None, ersacount=None,
                      sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None, clientauth=None,
                      clientcert=None, dhkeyexpsizelimit=None, sslredirect=None, redirectportrewrite=None, ssl3=None,
                      tls1=None, tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None,
                      commonname=None, pushenctrigger=None, sendclosenotify=None, cleartextport=None,
                      insertionencoding=None, denysslreneg=None, quantumsize=None, strictcachecks=None,
                      encrypttriggerpktcount=None, pushflag=None, dropreqwithnohostheader=None,
                      pushenctriggertimeout=None, ssltriggertimeout=None, clientauthuseboundcachain=None,
                      sessionticket=None, sessionticketlifetime=None, hsts=None, maxage=None, includesubdomains=None,
                      ciphername=None, cipherpriority=None, strictsigdigestcheck=None, save=False):
    '''
    Update the running configuration for the sslprofile config key.

    name(str): Name for the SSL profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must contain
        only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at (@), equals (=), and hyphen (-)
        characters. Cannot be changed after the profile is created. Minimum length = 1 Maximum length = 127

    sslprofiletype(str): Type of profile. Front end profiles apply to the entity that receives requests from a client.
        Backend profiles apply to the entity that sends client requests to a server. Default value: FrontEnd Possible
        values = BackEnd, FrontEnd

    dhcount(int): Number of interactions, between the client and the NetScaler appliance, after which the DH private-public
        pair is regenerated. A value of zero (0) specifies infinite use (no refresh). This parameter is not applicable
        when configuring a backend profile. Minimum value = 0 Maximum value = 65534

    dh(str): State of Diffie-Hellman (DH) key exchange. This parameter is not applicable when configuring a backend profile.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    dhfile(str): The file name and path for the DH parameter. Minimum length = 1

    ersa(str): State of Ephemeral RSA (eRSA) key exchange. Ephemeral RSA allows clients that support only export ciphers to
        communicate with the secure server even if the server certificate does not support export clients. The ephemeral
        RSA key is automatically generated when you bind an export cipher to an SSL or TCP-based SSL virtual server or
        service. When you remove the export cipher, the eRSA key is not deleted. It is reused at a later date when
        another export cipher is bound to an SSL or TCP-based SSL virtual server or service. The eRSA key is deleted when
        the appliance restarts. This parameter is not applicable when configuring a backend profile. Default value:
        ENABLED Possible values = ENABLED, DISABLED

    ersacount(int): The refresh count for the re-generation of RSA public-key and private-key pair. Minimum value = 0 Maximum
        value = 65534

    sessreuse(str): State of session reuse. Establishing the initial handshake requires CPU-intensive public key encryption
        operations. With the ENABLED setting, session key exchange is avoided for session resumption requests received
        from the client. Default value: ENABLED Possible values = ENABLED, DISABLED

    sesstimeout(int): The Session timeout value in seconds. Minimum value = 0 Maximum value = 4294967294

    cipherredirect(str): State of Cipher Redirect. If this parameter is set to ENABLED, you can configure an SSL virtual
        server or service to display meaningful error messages if the SSL handshake fails because of a cipher mismatch
        between the virtual server or service and the client. This parameter is not applicable when configuring a backend
        profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    cipherurl(str): The redirect URL to be used with the Cipher Redirect feature.

    clientauth(str): State of client authentication. In service-based SSL offload, the service terminates the SSL handshake
        if the SSL client does not provide a valid certificate.  This parameter is not applicable when configuring a
        backend profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    clientcert(str): The rule for client certificate requirement in client authentication. Possible values = Mandatory,
        Optional

    dhkeyexpsizelimit(str): This option enables the use of NIST recommended (NIST Special Publication 800-56A) bit size for
        private-key size. For example, for DH params of size 2048bit, the private-key size recommended is 224bits. This
        is rounded-up to 256bits. Default value: DISABLED Possible values = ENABLED, DISABLED

    sslredirect(str): State of HTTPS redirects for the SSL service.  For an SSL session, if the client browser receives a
        redirect message, the browser tries to connect to the new location. However, the secure SSL session breaks if the
        object has moved from a secure site (https://) to an unsecure site (http://). Typically, a warning message
        appears on the screen, prompting the user to continue or disconnect. If SSL Redirect is ENABLED, the redirect
        message is automatically converted from http:// to https:// and the SSL session does not break. This parameter is
        not applicable when configuring a backend profile. Default value: DISABLED Possible values = ENABLED, DISABLED

    redirectportrewrite(str): State of the port rewrite while performing HTTPS redirect. If this parameter is set to ENABLED,
        and the URL from the server does not contain the standard port, the port is rewritten to the standard. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    ssl3(str): State of SSLv3 protocol support for the SSL profile. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    tls1(str): State of TLSv1.0 protocol support for the SSL profile. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls11(str): State of TLSv1.1 protocol support for the SSL profile. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls12(str): State of TLSv1.2 protocol support for the SSL profile. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    snienable(str): State of the Server Name Indication (SNI) feature on the virtual server and service-based offload. SNI
        helps to enable SSL encryption on multiple domains on a single virtual server or service if the domains are
        controlled by the same organization and share the same second-level domain name. For example, *.sports.net can be
        used to secure domains such as login.sports.net and help.sports.net. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    ocspstapling(str): State of OCSP stapling support on the SSL virtual server. Supported only if the protocol used is
        higher than SSLv3. Possible values: ENABLED: The appliance sends a request to the OCSP responder to check the
        status of the server certificate and caches the response for the specified time. If the response is valid at the
        time of SSL handshake with the client, the OCSP-based server certificate status is sent to the client during the
        handshake. DISABLED: The appliance does not check the status of the server certificate. . Default value: DISABLED
        Possible values = ENABLED, DISABLED

    serverauth(str): State of server authentication support for the SSL Backend profile. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    commonname(str): Name to be checked against the CommonName (CN) field in the server certificate bound to the SSL server.
        Minimum length = 1

    pushenctrigger(str): Trigger encryption on the basis of the PUSH flag value. Available settings function as follows: *
        ALWAYS - Any PUSH packet triggers encryption. * IGNORE - Ignore PUSH packet for triggering encryption. * MERGE -
        For a consecutive sequence of PUSH packets, the last PUSH packet triggers encryption. * TIMER - PUSH packet
        triggering encryption is delayed by the time defined in the set ssl parameter command or in the Change Advanced
        SSL Settings dialog box. Possible values = Always, Merge, Ignore, Timer

    sendclosenotify(str): Enable sending SSL Close-Notify at the end of a transaction. Default value: YES Possible values =
        YES, NO

    cleartextport(int): Port on which clear-text data is sent by the appliance to the server. Do not specify this parameter
        for SSL offloading with end-to-end encryption. Range 1 - 65535 * in CLI is represented as 65535 in NITRO API

    insertionencoding(str): Encoding method used to insert the subject or issuers name in HTTP requests to servers. Default
        value: Unicode Possible values = Unicode, UTF-8

    denysslreneg(str): Deny renegotiation in specified circumstances. Available settings function as follows: * NO - Allow
        SSL renegotiation. * FRONTEND_CLIENT - Deny secure and nonsecure SSL renegotiation initiated by the client. *
        FRONTEND_CLIENTSERVER - Deny secure and nonsecure SSL renegotiation initiated by the client or the NetScaler
        during policy-based client authentication.  * ALL - Deny all secure and nonsecure SSL renegotiation. * NONSECURE
        - Deny nonsecure SSL renegotiation. Allows only clients that support RFC 5746. Default value: ALL Possible values
        = NO, FRONTEND_CLIENT, FRONTEND_CLIENTSERVER, ALL, NONSECURE

    quantumsize(str): Amount of data to collect before the data is pushed to the crypto hardware for encryption. For large
        downloads, a larger quantum size better utilizes the crypto resources. Default value: 8192 Possible values =
        4096, 8192, 16384

    strictcachecks(str): Enable strict CA certificate checks on the appliance. Default value: NO Possible values = YES, NO

    encrypttriggerpktcount(int): Maximum number of queued packets after which encryption is triggered. Use this setting for
        SSL transactions that send small packets from server to NetScaler. Default value: 45 Minimum value = 10 Maximum
        value = 50

    pushflag(int): Insert PUSH flag into decrypted, encrypted, or all records. If the PUSH flag is set to a value other than
        0, the buffered records are forwarded on the basis of the value of the PUSH flag. Available settings function as
        follows: 0 - Auto (PUSH flag is not set.) 1 - Insert PUSH flag into every decrypted record. 2 -Insert PUSH flag
        into every encrypted record. 3 - Insert PUSH flag into every decrypted and encrypted record. Minimum value = 0
        Maximum value = 3

    dropreqwithnohostheader(str): Host header check for SNI enabled sessions. If this check is enabled and the HTTP request
        does not contain the host header for SNI enabled sessions, the request is dropped. Default value: NO Possible
        values = YES, NO

    pushenctriggertimeout(int): PUSH encryption trigger timeout value. The timeout value is applied only if you set the Push
        Encryption Trigger parameter to Timer in the SSL virtual server settings. Default value: 1 Minimum value = 1
        Maximum value = 200

    ssltriggertimeout(int): Time, in milliseconds, after which encryption is triggered for transactions that are not tracked
        on the NetScaler appliance because their length is not known. There can be a delay of up to 10ms from the
        specified timeout value before the packet is pushed into the queue. Default value: 100 Minimum value = 1 Maximum
        value = 200

    clientauthuseboundcachain(str): Certficates bound on the VIP are used for validating the client cert. Certficates came
        along with client cert are not used for validating the client cert. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    sessionticket(str): This option enables the use of session tickets, as per the RFC 5077. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    sessionticketlifetime(int): This option sets the life time of session tickets issued by NS in secs. Default value: 300
        Minimum value = 0 Maximum value = 172800

    hsts(str): State of TLSv1.0 protocol support for the SSL Virtual Server. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    maxage(int): Set max-age value for STS header. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    includesubdomains(str): Set include sub domain value for STS header. Default value: NO Possible values = YES, NO

    ciphername(str): The cipher group/alias/individual cipher configuration.

    cipherpriority(int): cipher priority. Minimum value = 1

    strictsigdigestcheck(str): Parameter indicating to check whether peer entity certificate during TLS1.2 handshake is
        signed with one of signature-hash combination supported by Netscaler. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslprofile <args>

    '''

    result = {}

    payload = {'sslprofile': {}}

    if name:
        payload['sslprofile']['name'] = name

    if sslprofiletype:
        payload['sslprofile']['sslprofiletype'] = sslprofiletype

    if dhcount:
        payload['sslprofile']['dhcount'] = dhcount

    if dh:
        payload['sslprofile']['dh'] = dh

    if dhfile:
        payload['sslprofile']['dhfile'] = dhfile

    if ersa:
        payload['sslprofile']['ersa'] = ersa

    if ersacount:
        payload['sslprofile']['ersacount'] = ersacount

    if sessreuse:
        payload['sslprofile']['sessreuse'] = sessreuse

    if sesstimeout:
        payload['sslprofile']['sesstimeout'] = sesstimeout

    if cipherredirect:
        payload['sslprofile']['cipherredirect'] = cipherredirect

    if cipherurl:
        payload['sslprofile']['cipherurl'] = cipherurl

    if clientauth:
        payload['sslprofile']['clientauth'] = clientauth

    if clientcert:
        payload['sslprofile']['clientcert'] = clientcert

    if dhkeyexpsizelimit:
        payload['sslprofile']['dhkeyexpsizelimit'] = dhkeyexpsizelimit

    if sslredirect:
        payload['sslprofile']['sslredirect'] = sslredirect

    if redirectportrewrite:
        payload['sslprofile']['redirectportrewrite'] = redirectportrewrite

    if ssl3:
        payload['sslprofile']['ssl3'] = ssl3

    if tls1:
        payload['sslprofile']['tls1'] = tls1

    if tls11:
        payload['sslprofile']['tls11'] = tls11

    if tls12:
        payload['sslprofile']['tls12'] = tls12

    if snienable:
        payload['sslprofile']['snienable'] = snienable

    if ocspstapling:
        payload['sslprofile']['ocspstapling'] = ocspstapling

    if serverauth:
        payload['sslprofile']['serverauth'] = serverauth

    if commonname:
        payload['sslprofile']['commonname'] = commonname

    if pushenctrigger:
        payload['sslprofile']['pushenctrigger'] = pushenctrigger

    if sendclosenotify:
        payload['sslprofile']['sendclosenotify'] = sendclosenotify

    if cleartextport:
        payload['sslprofile']['cleartextport'] = cleartextport

    if insertionencoding:
        payload['sslprofile']['insertionencoding'] = insertionencoding

    if denysslreneg:
        payload['sslprofile']['denysslreneg'] = denysslreneg

    if quantumsize:
        payload['sslprofile']['quantumsize'] = quantumsize

    if strictcachecks:
        payload['sslprofile']['strictcachecks'] = strictcachecks

    if encrypttriggerpktcount:
        payload['sslprofile']['encrypttriggerpktcount'] = encrypttriggerpktcount

    if pushflag:
        payload['sslprofile']['pushflag'] = pushflag

    if dropreqwithnohostheader:
        payload['sslprofile']['dropreqwithnohostheader'] = dropreqwithnohostheader

    if pushenctriggertimeout:
        payload['sslprofile']['pushenctriggertimeout'] = pushenctriggertimeout

    if ssltriggertimeout:
        payload['sslprofile']['ssltriggertimeout'] = ssltriggertimeout

    if clientauthuseboundcachain:
        payload['sslprofile']['clientauthuseboundcachain'] = clientauthuseboundcachain

    if sessionticket:
        payload['sslprofile']['sessionticket'] = sessionticket

    if sessionticketlifetime:
        payload['sslprofile']['sessionticketlifetime'] = sessionticketlifetime

    if hsts:
        payload['sslprofile']['hsts'] = hsts

    if maxage:
        payload['sslprofile']['maxage'] = maxage

    if includesubdomains:
        payload['sslprofile']['includesubdomains'] = includesubdomains

    if ciphername:
        payload['sslprofile']['ciphername'] = ciphername

    if cipherpriority:
        payload['sslprofile']['cipherpriority'] = cipherpriority

    if strictsigdigestcheck:
        payload['sslprofile']['strictsigdigestcheck'] = strictsigdigestcheck

    execution = __proxy__['citrixns.put']('config/sslprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslservice(servicename=None, dh=None, dhfile=None, dhcount=None, dhkeyexpsizelimit=None, ersa=None,
                      ersacount=None, sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None,
                      sslv2redirect=None, sslv2url=None, clientauth=None, clientcert=None, sslredirect=None,
                      redirectportrewrite=None, ssl2=None, ssl3=None, tls1=None, tls11=None, tls12=None, snienable=None,
                      ocspstapling=None, serverauth=None, commonname=None, pushenctrigger=None, sendclosenotify=None,
                      dtlsprofilename=None, sslprofile=None, strictsigdigestcheck=None, save=False):
    '''
    Update the running configuration for the sslservice config key.

    servicename(str): Name of the SSL service. Minimum length = 1

    dh(str): State of Diffie-Hellman (DH) key exchange. This parameter is not applicable when configuring a backend service.
        Default value: DISABLED Possible values = ENABLED, DISABLED

    dhfile(str): Name for and, optionally, path to the PEM-format DH parameter file to be installed. /nsconfig/ssl/ is the
        default path. This parameter is not applicable when configuring a backend service. Minimum length = 1

    dhcount(int): Number of interactions, between the client and the NetScaler appliance, after which the DH private-public
        pair is regenerated. A value of zero (0) specifies infinite use (no refresh). This parameter is not applicable
        when configuring a backend service. Minimum value = 0 Maximum value = 65534

    dhkeyexpsizelimit(str): This option enables the use of NIST recommended (NIST Special Publication 800-56A) bit size for
        private-key size. For example, for DH params of size 2048bit, the private-key size recommended is 224bits. This
        is rounded-up to 256bits. Default value: DISABLED Possible values = ENABLED, DISABLED

    ersa(str): State of Ephemeral RSA (eRSA) key exchange. Ephemeral RSA allows clients that support only export ciphers to
        communicate with the secure server even if the server certificate does not support export clients. The ephemeral
        RSA key is automatically generated when you bind an export cipher to an SSL or TCP-based SSL virtual server or
        service. When you remove the export cipher, the eRSA key is not deleted. It is reused at a later date when
        another export cipher is bound to an SSL or TCP-based SSL virtual server or service. The eRSA key is deleted when
        the appliance restarts. This parameter is not applicable when configuring a backend service. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    ersacount(int): Refresh count for regeneration of RSA public-key and private-key pair. Zero (0) specifies infinite usage
        (no refresh).  This parameter is not applicable when configuring a backend service. Minimum value = 0 Maximum
        value = 65534

    sessreuse(str): State of session reuse. Establishing the initial handshake requires CPU-intensive public key encryption
        operations. With the ENABLED setting, session key exchange is avoided for session resumption requests received
        from the client. Default value: ENABLED Possible values = ENABLED, DISABLED

    sesstimeout(int): Time, in seconds, for which to keep the session active. Any session resumption request received after
        the timeout period will require a fresh SSL handshake and establishment of a new SSL session. Default value: 300
        Minimum value = 0 Maximum value = 4294967294

    cipherredirect(str): State of Cipher Redirect. If this parameter is set to ENABLED, you can configure an SSL virtual
        server or service to display meaningful error messages if the SSL handshake fails because of a cipher mismatch
        between the virtual server or service and the client. This parameter is not applicable when configuring a backend
        service. Default value: DISABLED Possible values = ENABLED, DISABLED

    cipherurl(str): URL of the page to which to redirect the client in case of a cipher mismatch. Typically, this page has a
        clear explanation of the error or an alternative location that the transaction can continue from. This parameter
        is not applicable when configuring a backend service.

    sslv2redirect(str): State of SSLv2 Redirect. If this parameter is set to ENABLED, you can configure an SSL virtual server
        or service to display meaningful error messages if the SSL handshake fails because of a protocol version mismatch
        between the virtual server or service and the client. This parameter is not applicable when configuring a backend
        service. Default value: DISABLED Possible values = ENABLED, DISABLED

    sslv2url(str): URL of the page to which to redirect the client in case of a protocol version mismatch. Typically, this
        page has a clear explanation of the error or an alternative location that the transaction can continue from. This
        parameter is not applicable when configuring a backend service.

    clientauth(str): State of client authentication. In service-based SSL offload, the service terminates the SSL handshake
        if the SSL client does not provide a valid certificate.  This parameter is not applicable when configuring a
        backend service. Default value: DISABLED Possible values = ENABLED, DISABLED

    clientcert(str): Type of client authentication. If this parameter is set to MANDATORY, the appliance terminates the SSL
        handshake if the SSL client does not provide a valid certificate. With the OPTIONAL setting, the appliance
        requests a certificate from the SSL clients but proceeds with the SSL transaction even if the client presents an
        invalid certificate. This parameter is not applicable when configuring a backend SSL service. Caution: Define
        proper access control policies before changing this setting to Optional. Possible values = Mandatory, Optional

    sslredirect(str): State of HTTPS redirects for the SSL service.   For an SSL session, if the client browser receives a
        redirect message, the browser tries to connect to the new location. However, the secure SSL session breaks if the
        object has moved from a secure site (https://) to an unsecure site (http://). Typically, a warning message
        appears on the screen, prompting the user to continue or disconnect. If SSL Redirect is ENABLED, the redirect
        message is automatically converted from http:// to https:// and the SSL session does not break.  This parameter
        is not applicable when configuring a backend service. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    redirectportrewrite(str): State of the port rewrite while performing HTTPS redirect. If this parameter is set to ENABLED,
        and the URL from the server does not contain the standard port, the port is rewritten to the standard. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    ssl2(str): State of SSLv2 protocol support for the SSL service. This parameter is not applicable when configuring a
        backend service. Default value: DISABLED Possible values = ENABLED, DISABLED

    ssl3(str): State of SSLv3 protocol support for the SSL service. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls1(str): State of TLSv1.0 protocol support for the SSL service. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls11(str): State of TLSv1.1 protocol support for the SSL service. Enabled for Front-end service on MPX-CVM platform
        only. Default value: ENABLED Possible values = ENABLED, DISABLED

    tls12(str): State of TLSv1.2 protocol support for the SSL service. Enabled for Front-end service on MPX-CVM platform
        only. Default value: ENABLED Possible values = ENABLED, DISABLED

    snienable(str): State of the Server Name Indication (SNI) feature on the virtual server and service-based offload. SNI
        helps to enable SSL encryption on multiple domains on a single virtual server or service if the domains are
        controlled by the same organization and share the same second-level domain name. For example, *.sports.net can be
        used to secure domains such as login.sports.net and help.sports.net. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    ocspstapling(str): State of OCSP stapling support on the SSL virtual server. Supported only if the protocol used is
        higher than SSLv3. Possible values: ENABLED: The appliance sends a request to the OCSP responder to check the
        status of the server certificate and caches the response for the specified time. If the response is valid at the
        time of SSL handshake with the client, the OCSP-based server certificate status is sent to the client during the
        handshake. DISABLED: The appliance does not check the status of the server certificate. . Default value: DISABLED
        Possible values = ENABLED, DISABLED

    serverauth(str): State of server authentication support for the SSL service. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    commonname(str): Name to be checked against the CommonName (CN) field in the server certificate bound to the SSL server.
        Minimum length = 1

    pushenctrigger(str): Trigger encryption on the basis of the PUSH flag value. Available settings function as follows: *
        ALWAYS - Any PUSH packet triggers encryption. * IGNORE - Ignore PUSH packet for triggering encryption. * MERGE -
        For a consecutive sequence of PUSH packets, the last PUSH packet triggers encryption. * TIMER - PUSH packet
        triggering encryption is delayed by the time defined in the set ssl parameter command or in the Change Advanced
        SSL Settings dialog box. Possible values = Always, Merge, Ignore, Timer

    sendclosenotify(str): Enable sending SSL Close-Notify at the end of a transaction. Default value: YES Possible values =
        YES, NO

    dtlsprofilename(str): Name of the DTLS profile that contains DTLS settings for the service. Minimum length = 1 Maximum
        length = 127

    sslprofile(str): Name of the SSL profile that contains SSL settings for the service. Minimum length = 1 Maximum length =
        127

    strictsigdigestcheck(str): Parameter indicating to check whether peers certificate during TLS1.2 handshake is signed with
        one of signature-hash combination supported by Netscaler. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslservice <args>

    '''

    result = {}

    payload = {'sslservice': {}}

    if servicename:
        payload['sslservice']['servicename'] = servicename

    if dh:
        payload['sslservice']['dh'] = dh

    if dhfile:
        payload['sslservice']['dhfile'] = dhfile

    if dhcount:
        payload['sslservice']['dhcount'] = dhcount

    if dhkeyexpsizelimit:
        payload['sslservice']['dhkeyexpsizelimit'] = dhkeyexpsizelimit

    if ersa:
        payload['sslservice']['ersa'] = ersa

    if ersacount:
        payload['sslservice']['ersacount'] = ersacount

    if sessreuse:
        payload['sslservice']['sessreuse'] = sessreuse

    if sesstimeout:
        payload['sslservice']['sesstimeout'] = sesstimeout

    if cipherredirect:
        payload['sslservice']['cipherredirect'] = cipherredirect

    if cipherurl:
        payload['sslservice']['cipherurl'] = cipherurl

    if sslv2redirect:
        payload['sslservice']['sslv2redirect'] = sslv2redirect

    if sslv2url:
        payload['sslservice']['sslv2url'] = sslv2url

    if clientauth:
        payload['sslservice']['clientauth'] = clientauth

    if clientcert:
        payload['sslservice']['clientcert'] = clientcert

    if sslredirect:
        payload['sslservice']['sslredirect'] = sslredirect

    if redirectportrewrite:
        payload['sslservice']['redirectportrewrite'] = redirectportrewrite

    if ssl2:
        payload['sslservice']['ssl2'] = ssl2

    if ssl3:
        payload['sslservice']['ssl3'] = ssl3

    if tls1:
        payload['sslservice']['tls1'] = tls1

    if tls11:
        payload['sslservice']['tls11'] = tls11

    if tls12:
        payload['sslservice']['tls12'] = tls12

    if snienable:
        payload['sslservice']['snienable'] = snienable

    if ocspstapling:
        payload['sslservice']['ocspstapling'] = ocspstapling

    if serverauth:
        payload['sslservice']['serverauth'] = serverauth

    if commonname:
        payload['sslservice']['commonname'] = commonname

    if pushenctrigger:
        payload['sslservice']['pushenctrigger'] = pushenctrigger

    if sendclosenotify:
        payload['sslservice']['sendclosenotify'] = sendclosenotify

    if dtlsprofilename:
        payload['sslservice']['dtlsprofilename'] = dtlsprofilename

    if sslprofile:
        payload['sslservice']['sslprofile'] = sslprofile

    if strictsigdigestcheck:
        payload['sslservice']['strictsigdigestcheck'] = strictsigdigestcheck

    execution = __proxy__['citrixns.put']('config/sslservice', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslservicegroup(servicegroupname=None, sslprofile=None, sessreuse=None, sesstimeout=None, ssl3=None,
                           tls1=None, tls11=None, tls12=None, snienable=None, ocspstapling=None, serverauth=None,
                           commonname=None, sendclosenotify=None, strictsigdigestcheck=None, save=False):
    '''
    Update the running configuration for the sslservicegroup config key.

    servicegroupname(str): Name of the SSL service group for which to set advanced configuration. Minimum length = 1

    sslprofile(str): Name of the SSL profile that contains SSL settings for the Service Group. Minimum length = 1 Maximum
        length = 127

    sessreuse(str): State of session reuse. Establishing the initial handshake requires CPU-intensive public key encryption
        operations. With the ENABLED setting, session key exchange is avoided for session resumption requests received
        from the client. Default value: ENABLED Possible values = ENABLED, DISABLED

    sesstimeout(int): Time, in seconds, for which to keep the session active. Any session resumption request received after
        the timeout period will require a fresh SSL handshake and establishment of a new SSL session. Default value: 300
        Minimum value = 0 Maximum value = 4294967294

    ssl3(str): State of SSLv3 protocol support for the SSL service group. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls1(str): State of TLSv1.0 protocol support for the SSL service group. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls11(str): State of TLSv1.1 protocol support for the SSL service group. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    tls12(str): State of TLSv1.2 protocol support for the SSL service group. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    snienable(str): State of the Server Name Indication (SNI) feature on the service. SNI helps to enable SSL encryption on
        multiple domains on a single virtual server or service if the domains are controlled by the same organization and
        share the same second-level domain name. For example, *.sports.net can be used to secure domains such as
        login.sports.net and help.sports.net. Default value: DISABLED Possible values = ENABLED, DISABLED

    ocspstapling(str): State of OCSP stapling support on the SSL virtual server. Supported only if the protocol used is
        higher than SSLv3. Possible values: ENABLED: The appliance sends a request to the OCSP responder to check the
        status of the server certificate and caches the response for the specified time. If the response is valid at the
        time of SSL handshake with the client, the OCSP-based server certificate status is sent to the client during the
        handshake. DISABLED: The appliance does not check the status of the server certificate. Default value: DISABLED
        Possible values = ENABLED, DISABLED

    serverauth(str): State of server authentication support for the SSL service group. Default value: DISABLED Possible
        values = ENABLED, DISABLED

    commonname(str): Name to be checked against the CommonName (CN) field in the server certificate bound to the SSL server.
        Minimum length = 1

    sendclosenotify(str): Enable sending SSL Close-Notify at the end of a transaction. Default value: YES Possible values =
        YES, NO

    strictsigdigestcheck(str): Parameter indicating to check whether peers certificate is signed with one of signature-hash
        combination supported by Netscaler. Default value: DISABLED Possible values = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslservicegroup <args>

    '''

    result = {}

    payload = {'sslservicegroup': {}}

    if servicegroupname:
        payload['sslservicegroup']['servicegroupname'] = servicegroupname

    if sslprofile:
        payload['sslservicegroup']['sslprofile'] = sslprofile

    if sessreuse:
        payload['sslservicegroup']['sessreuse'] = sessreuse

    if sesstimeout:
        payload['sslservicegroup']['sesstimeout'] = sesstimeout

    if ssl3:
        payload['sslservicegroup']['ssl3'] = ssl3

    if tls1:
        payload['sslservicegroup']['tls1'] = tls1

    if tls11:
        payload['sslservicegroup']['tls11'] = tls11

    if tls12:
        payload['sslservicegroup']['tls12'] = tls12

    if snienable:
        payload['sslservicegroup']['snienable'] = snienable

    if ocspstapling:
        payload['sslservicegroup']['ocspstapling'] = ocspstapling

    if serverauth:
        payload['sslservicegroup']['serverauth'] = serverauth

    if commonname:
        payload['sslservicegroup']['commonname'] = commonname

    if sendclosenotify:
        payload['sslservicegroup']['sendclosenotify'] = sendclosenotify

    if strictsigdigestcheck:
        payload['sslservicegroup']['strictsigdigestcheck'] = strictsigdigestcheck

    execution = __proxy__['citrixns.put']('config/sslservicegroup', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_sslvserver(vservername=None, cleartextport=None, dh=None, dhfile=None, dhcount=None, dhkeyexpsizelimit=None,
                      ersa=None, ersacount=None, sessreuse=None, sesstimeout=None, cipherredirect=None, cipherurl=None,
                      sslv2redirect=None, sslv2url=None, clientauth=None, clientcert=None, sslredirect=None,
                      redirectportrewrite=None, ssl2=None, ssl3=None, tls1=None, tls11=None, tls12=None, snienable=None,
                      ocspstapling=None, pushenctrigger=None, sendclosenotify=None, dtlsprofilename=None,
                      sslprofile=None, hsts=None, maxage=None, includesubdomains=None, strictsigdigestcheck=None,
                      save=False):
    '''
    Update the running configuration for the sslvserver config key.

    vservername(str): Name of the SSL virtual server for which to set advanced configuration. Minimum length = 1

    cleartextport(int): Port on which clear-text data is sent by the appliance to the server. Do not specify this parameter
        for SSL offloading with end-to-end encryption. Default value: 0 Minimum value = 0 Maximum value = 65534

    dh(str): State of Diffie-Hellman (DH) key exchange. Default value: DISABLED Possible values = ENABLED, DISABLED

    dhfile(str): Name of and, optionally, path to the DH parameter file, in PEM format, to be installed. /nsconfig/ssl/ is
        the default path. Minimum length = 1

    dhcount(int): Number of interactions, between the client and the NetScaler appliance, after which the DH private-public
        pair is regenerated. A value of zero (0) specifies infinite use (no refresh). Minimum value = 0 Maximum value =
        65534

    dhkeyexpsizelimit(str): This option enables the use of NIST recommended (NIST Special Publication 800-56A) bit size for
        private-key size. For example, for DH params of size 2048bit, the private-key size recommended is 224bits. This
        is rounded-up to 256bits. Default value: DISABLED Possible values = ENABLED, DISABLED

    ersa(str): State of Ephemeral RSA (eRSA) key exchange. Ephemeral RSA allows clients that support only export ciphers to
        communicate with the secure server even if the server certificate does not support export clients. The ephemeral
        RSA key is automatically generated when you bind an export cipher to an SSL or TCP-based SSL virtual server or
        service. When you remove the export cipher, the eRSA key is not deleted. It is reused at a later date when
        another export cipher is bound to an SSL or TCP-based SSL virtual server or service. The eRSA key is deleted when
        the appliance restarts. Default value: ENABLED Possible values = ENABLED, DISABLED

    ersacount(int): Refresh count for regeneration of the RSA public-key and private-key pair. Zero (0) specifies infinite
        usage (no refresh). Minimum value = 0 Maximum value = 65534

    sessreuse(str): State of session reuse. Establishing the initial handshake requires CPU-intensive public key encryption
        operations. With the ENABLED setting, session key exchange is avoided for session resumption requests received
        from the client. Default value: ENABLED Possible values = ENABLED, DISABLED

    sesstimeout(int): Time, in seconds, for which to keep the session active. Any session resumption request received after
        the timeout period will require a fresh SSL handshake and establishment of a new SSL session. Default value: 120
        Minimum value = 0 Maximum value = 4294967294

    cipherredirect(str): State of Cipher Redirect. If cipher redirect is enabled, you can configure an SSL virtual server or
        service to display meaningful error messages if the SSL handshake fails because of a cipher mismatch between the
        virtual server or service and the client. Default value: DISABLED Possible values = ENABLED, DISABLED

    cipherurl(str): The redirect URL to be used with the Cipher Redirect feature.

    sslv2redirect(str): State of SSLv2 Redirect. If SSLv2 redirect is enabled, you can configure an SSL virtual server or
        service to display meaningful error messages if the SSL handshake fails because of a protocol version mismatch
        between the virtual server or service and the client. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    sslv2url(str): URL of the page to which to redirect the client in case of a protocol version mismatch. Typically, this
        page has a clear explanation of the error or an alternative location that the transaction can continue from.

    clientauth(str): State of client authentication. If client authentication is enabled, the virtual server terminates the
        SSL handshake if the SSL client does not provide a valid certificate. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    clientcert(str): Type of client authentication. If this parameter is set to MANDATORY, the appliance terminates the SSL
        handshake if the SSL client does not provide a valid certificate. With the OPTIONAL setting, the appliance
        requests a certificate from the SSL clients but proceeds with the SSL transaction even if the client presents an
        invalid certificate. Caution: Define proper access control policies before changing this setting to Optional.
        Possible values = Mandatory, Optional

    sslredirect(str): State of HTTPS redirects for the SSL virtual server.   For an SSL session, if the client browser
        receives a redirect message, the browser tries to connect to the new location. However, the secure SSL session
        breaks if the object has moved from a secure site (https://) to an unsecure site (http://). Typically, a warning
        message appears on the screen, prompting the user to continue or disconnect. If SSL Redirect is ENABLED, the
        redirect message is automatically converted from http:// to https:// and the SSL session does not break. Default
        value: DISABLED Possible values = ENABLED, DISABLED

    redirectportrewrite(str): State of the port rewrite while performing HTTPS redirect. If this parameter is ENABLED and the
        URL from the server does not contain the standard port, the port is rewritten to the standard. Default value:
        DISABLED Possible values = ENABLED, DISABLED

    ssl2(str): State of SSLv2 protocol support for the SSL Virtual Server. Default value: DISABLED Possible values = ENABLED,
        DISABLED

    ssl3(str): State of SSLv3 protocol support for the SSL Virtual Server. Default value: ENABLED Possible values = ENABLED,
        DISABLED

    tls1(str): State of TLSv1.0 protocol support for the SSL Virtual Server. Default value: ENABLED Possible values =
        ENABLED, DISABLED

    tls11(str): State of TLSv1.1 protocol support for the SSL Virtual Server. TLSv1.1 protocol is supported only on the MPX
        appliance. Support is not available on a FIPS appliance or on a NetScaler VPX virtual appliance. On an SDX
        appliance, TLSv1.1 protocol is supported only if an SSL chip is assigned to the instance. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    tls12(str): State of TLSv1.2 protocol support for the SSL Virtual Server. TLSv1.2 protocol is supported only on the MPX
        appliance. Support is not available on a FIPS appliance or on a NetScaler VPX virtual appliance. On an SDX
        appliance, TLSv1.2 protocol is supported only if an SSL chip is assigned to the instance. Default value: ENABLED
        Possible values = ENABLED, DISABLED

    snienable(str): State of the Server Name Indication (SNI) feature on the virtual server and service-based offload. SNI
        helps to enable SSL encryption on multiple domains on a single virtual server or service if the domains are
        controlled by the same organization and share the same second-level domain name. For example, *.sports.net can be
        used to secure domains such as login.sports.net and help.sports.net. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    ocspstapling(str): State of OCSP stapling support on the SSL virtual server. Supported only if the protocol used is
        higher than SSLv3. Possible values: ENABLED: The appliance sends a request to the OCSP responder to check the
        status of the server certificate and caches the response for the specified time. If the response is valid at the
        time of SSL handshake with the client, the OCSP-based server certificate status is sent to the client during the
        handshake. DISABLED: The appliance does not check the status of the server certificate. . Default value: DISABLED
        Possible values = ENABLED, DISABLED

    pushenctrigger(str): Trigger encryption on the basis of the PUSH flag value. Available settings function as follows: *
        ALWAYS - Any PUSH packet triggers encryption. * IGNORE - Ignore PUSH packet for triggering encryption. * MERGE -
        For a consecutive sequence of PUSH packets, the last PUSH packet triggers encryption. * TIMER - PUSH packet
        triggering encryption is delayed by the time defined in the set ssl parameter command or in the Change Advanced
        SSL Settings dialog box. Possible values = Always, Merge, Ignore, Timer

    sendclosenotify(str): Enable sending SSL Close-Notify at the end of a transaction. Default value: YES Possible values =
        YES, NO

    dtlsprofilename(str): Name of the DTLS profile whose settings are to be applied to the virtual server. Minimum length = 1
        Maximum length = 127

    sslprofile(str): Name of the SSL profile that contains SSL settings for the virtual server. Minimum length = 1 Maximum
        length = 127

    hsts(str): State of TLSv1.0 protocol support for the SSL Virtual Server. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    maxage(int): Set max-age value for STS header. Default value: 0 Minimum value = 0 Maximum value = 4294967294

    includesubdomains(str): Set include sub domain value for STS header. Default value: NO Possible values = YES, NO

    strictsigdigestcheck(str): Parameter indicating to check whether peer entity certificate during TLS1.2 handshake is
        signed with one of signature-hash combination supported by Netscaler. Default value: DISABLED Possible values =
        ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' ssl.update_sslvserver <args>

    '''

    result = {}

    payload = {'sslvserver': {}}

    if vservername:
        payload['sslvserver']['vservername'] = vservername

    if cleartextport:
        payload['sslvserver']['cleartextport'] = cleartextport

    if dh:
        payload['sslvserver']['dh'] = dh

    if dhfile:
        payload['sslvserver']['dhfile'] = dhfile

    if dhcount:
        payload['sslvserver']['dhcount'] = dhcount

    if dhkeyexpsizelimit:
        payload['sslvserver']['dhkeyexpsizelimit'] = dhkeyexpsizelimit

    if ersa:
        payload['sslvserver']['ersa'] = ersa

    if ersacount:
        payload['sslvserver']['ersacount'] = ersacount

    if sessreuse:
        payload['sslvserver']['sessreuse'] = sessreuse

    if sesstimeout:
        payload['sslvserver']['sesstimeout'] = sesstimeout

    if cipherredirect:
        payload['sslvserver']['cipherredirect'] = cipherredirect

    if cipherurl:
        payload['sslvserver']['cipherurl'] = cipherurl

    if sslv2redirect:
        payload['sslvserver']['sslv2redirect'] = sslv2redirect

    if sslv2url:
        payload['sslvserver']['sslv2url'] = sslv2url

    if clientauth:
        payload['sslvserver']['clientauth'] = clientauth

    if clientcert:
        payload['sslvserver']['clientcert'] = clientcert

    if sslredirect:
        payload['sslvserver']['sslredirect'] = sslredirect

    if redirectportrewrite:
        payload['sslvserver']['redirectportrewrite'] = redirectportrewrite

    if ssl2:
        payload['sslvserver']['ssl2'] = ssl2

    if ssl3:
        payload['sslvserver']['ssl3'] = ssl3

    if tls1:
        payload['sslvserver']['tls1'] = tls1

    if tls11:
        payload['sslvserver']['tls11'] = tls11

    if tls12:
        payload['sslvserver']['tls12'] = tls12

    if snienable:
        payload['sslvserver']['snienable'] = snienable

    if ocspstapling:
        payload['sslvserver']['ocspstapling'] = ocspstapling

    if pushenctrigger:
        payload['sslvserver']['pushenctrigger'] = pushenctrigger

    if sendclosenotify:
        payload['sslvserver']['sendclosenotify'] = sendclosenotify

    if dtlsprofilename:
        payload['sslvserver']['dtlsprofilename'] = dtlsprofilename

    if sslprofile:
        payload['sslvserver']['sslprofile'] = sslprofile

    if hsts:
        payload['sslvserver']['hsts'] = hsts

    if maxage:
        payload['sslvserver']['maxage'] = maxage

    if includesubdomains:
        payload['sslvserver']['includesubdomains'] = includesubdomains

    if strictsigdigestcheck:
        payload['sslvserver']['strictsigdigestcheck'] = strictsigdigestcheck

    execution = __proxy__['citrixns.put']('config/sslvserver', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
