# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the webinterface key.

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

__virtualname__ = 'webinterface'


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

    return False, 'The webinterface execution module can only be loaded for citrixns proxy minions.'


def add_wisite(sitepath=None, agurl=None, staurl=None, secondstaurl=None, sessionreliability=None, usetwotickets=None,
               authenticationpoint=None, agauthenticationmethod=None, wiauthenticationmethods=None,
               defaultcustomtextlocale=None, websessiontimeout=None, defaultaccessmethod=None, logintitle=None,
               appwelcomemessage=None, welcomemessage=None, footertext=None, loginsysmessage=None, preloginbutton=None,
               preloginmessage=None, prelogintitle=None, domainselection=None, sitetype=None, userinterfacebranding=None,
               publishedresourcetype=None, kioskmode=None, showsearch=None, showrefresh=None, wiuserinterfacemodes=None,
               userinterfacelayouts=None, restrictdomains=None, logindomains=None, hidedomainfield=None,
               agcallbackurl=None, save=False):
    '''
    Add a new wisite to the running configuration.

    sitepath(str): Path to the Web Interface site being created on the NetScaler appliance. Minimum length = 1 Maximum length
        = 250

    agurl(str): Call back URL of the Gateway. Minimum length = 1 Maximum length = 255

    staurl(str): URL of the Secure Ticket Authority (STA) server. Minimum length = 1 Maximum length = 255

    secondstaurl(str): URL of the second Secure Ticket Authority (STA) server. Minimum length = 1 Maximum length = 255

    sessionreliability(str): Enable session reliability through Access Gateway. Default value: OFF Possible values = ON, OFF

    usetwotickets(str): Request tickets issued by two separate Secure Ticket Authorities (STA) when a resource is accessed.
        Default value: OFF Possible values = ON, OFF

    authenticationpoint(str): Authentication point for the Web Interface site. Possible values = WebInterface, AccessGateway

    agauthenticationmethod(str): Method for authenticating a Web Interface site if you have specified Web Interface as the
        authentication point.  Available settings function as follows:  * Explicit - Users must provide a user name and
        password to log on to the Web Interface.  * Anonymous - Users can log on to the Web Interface without providing a
        user name and password. They have access to resources published for anonymous users. Possible values = Explicit,
        SmartCard

    wiauthenticationmethods(list(str)): The method of authentication to be used at Web Interface. Default value: Explicit
        Possible values = Explicit, Anonymous

    defaultcustomtextlocale(str): Default language for the Web Interface site. Default value: English Possible values =
        German, English, Spanish, French, Japanese, Korean, Russian, Chinese_simplified, Chinese_traditional

    websessiontimeout(int): Time-out, in minutes, for idle Web Interface browser sessions. If a clients session is idle for a
        time that exceeds the time-out value, the NetScaler appliance terminates the connection. Default value: 20
        Minimum value = 1 Maximum value = 1440

    defaultaccessmethod(str): Default access method for clients accessing the Web Interface site.    Note: Before you
        configure an access method based on the client IP address, you must enable USIP mode on the Web Interface service
        to make the clients IP address available with the Web Interface.  Depending on whether the Web Interface site is
        configured to use an HTTP or HTTPS virtual server or to use access gateway, you can send clients or access
        gateway the IP address, or the alternate address, of a XenApp or XenDesktop server. Or, you can send the IP
        address translated from a mapping entry, which defines mapping of an internal address and port to an external
        address and port.  Note: In the NetScaler command line, mapping entries can be created by using the bind wi site
        command. Possible values = Direct, Alternate, Translated, GatewayDirect, GatewayAlternate, GatewayTranslated

    logintitle(str): A custom login page title for the Web Interface site. Default value: "Welcome to Web Interface on
        NetScaler" Minimum length = 1 Maximum length = 255

    appwelcomemessage(str): Specifies localized text to appear at the top of the main content area of the Applications
        screen. LanguageCode is en, de, es, fr, ja, or any other supported language identifier. Minimum length = 1
        Maximum length = 255

    welcomemessage(str): Localized welcome message that appears on the welcome area of the login screen. Minimum length = 1
        Maximum length = 255

    footertext(str): Localized text that appears in the footer area of all pages. Minimum length = 1 Maximum length = 255

    loginsysmessage(str): Localized text that appears at the bottom of the main content area of the login screen. Minimum
        length = 1 Maximum length = 255

    preloginbutton(str): Localized text that appears as the name of the pre-login message confirmation button. Minimum length
        = 1 Maximum length = 255

    preloginmessage(str): Localized text that appears on the pre-login message page. Minimum length = 1 Maximum length =
        2048

    prelogintitle(str): Localized text that appears as the title of the pre-login message page. Minimum length = 1 Maximum
        length = 255

    domainselection(str): Domain names listed on the login screen for explicit authentication. Minimum length = 1 Maximum
        length = 255

    sitetype(str): Type of access to the Web Interface site. Available settings function as follows: * XenApp/XenDesktop web
        site - Configures the Web Interface site for access by a web browser. * XenApp/XenDesktop services site -
        Configures the Web Interface site for access by the XenApp plug-in. Default value: XenAppWeb Possible values =
        XenAppWeb, XenAppServices

    userinterfacebranding(str): Specifies whether the site is focused towards users accessing applications or desktops.
        Setting the parameter to Desktops changes the functionality of the site to improve the experience for XenDesktop
        users. Citrix recommends using this setting for any deployment that includes XenDesktop. Default value:
        Applications Possible values = Desktops, Applications

    publishedresourcetype(str): Method for accessing the published XenApp and XenDesktop resources.   Available settings
        function as follows:  * Online - Allows applications to be launched on the XenApp and XenDesktop servers.   *
        Offline - Allows streaming of applications to the client.   * DualMode - Allows both online and offline modes.
        Default value: Online Possible values = Online, Offline, DualMode

    kioskmode(str): User settings do not persist from one session to another. Default value: OFF Possible values = ON, OFF

    showsearch(str): Enables search option on XenApp websites. Default value: OFF Possible values = ON, OFF

    showrefresh(str): Provides the Refresh button on the applications screen. Default value: OFF Possible values = ON, OFF

    wiuserinterfacemodes(str): Appearance of the login screen.  * Simple - Only the login fields for the selected
        authentication method are displayed.  * Advanced - Displays the navigation bar, which provides access to the
        pre-login messages and preferences screens. Default value: SIMPLE Possible values = SIMPLE, ADVANCED

    userinterfacelayouts(str): Specifies whether or not to use the compact user interface. Default value: AUTO Possible
        values = AUTO, NORMAL, COMPACT

    restrictdomains(str): The RestrictDomains setting is used to enable/disable domain restrictions. If domain restriction is
        enabled, the LoginDomains list is used for validating the login domain. It is applied to all the authentication
        methods except Anonymous for XenApp Web and XenApp Services sites. Default value: OFF Possible values = ON, OFF

    logindomains(str): [List of NetBIOS domain names], Domain names to use for access restriction.  Only takes effect when
        used in conjunction with the RestrictDomains setting. Minimum length = 1 Maximum length = 255

    hidedomainfield(str): The HideDomainField setting is used to control whether the domain field is displayed on the logon
        screen. Default value: OFF Possible values = ON, OFF

    agcallbackurl(str): Callback AGURL to which Web Interface contacts. . Minimum length = 1 Maximum length = 255

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.add_wisite <args>

    '''

    result = {}

    payload = {'wisite': {}}

    if sitepath:
        payload['wisite']['sitepath'] = sitepath

    if agurl:
        payload['wisite']['agurl'] = agurl

    if staurl:
        payload['wisite']['staurl'] = staurl

    if secondstaurl:
        payload['wisite']['secondstaurl'] = secondstaurl

    if sessionreliability:
        payload['wisite']['sessionreliability'] = sessionreliability

    if usetwotickets:
        payload['wisite']['usetwotickets'] = usetwotickets

    if authenticationpoint:
        payload['wisite']['authenticationpoint'] = authenticationpoint

    if agauthenticationmethod:
        payload['wisite']['agauthenticationmethod'] = agauthenticationmethod

    if wiauthenticationmethods:
        payload['wisite']['wiauthenticationmethods'] = wiauthenticationmethods

    if defaultcustomtextlocale:
        payload['wisite']['defaultcustomtextlocale'] = defaultcustomtextlocale

    if websessiontimeout:
        payload['wisite']['websessiontimeout'] = websessiontimeout

    if defaultaccessmethod:
        payload['wisite']['defaultaccessmethod'] = defaultaccessmethod

    if logintitle:
        payload['wisite']['logintitle'] = logintitle

    if appwelcomemessage:
        payload['wisite']['appwelcomemessage'] = appwelcomemessage

    if welcomemessage:
        payload['wisite']['welcomemessage'] = welcomemessage

    if footertext:
        payload['wisite']['footertext'] = footertext

    if loginsysmessage:
        payload['wisite']['loginsysmessage'] = loginsysmessage

    if preloginbutton:
        payload['wisite']['preloginbutton'] = preloginbutton

    if preloginmessage:
        payload['wisite']['preloginmessage'] = preloginmessage

    if prelogintitle:
        payload['wisite']['prelogintitle'] = prelogintitle

    if domainselection:
        payload['wisite']['domainselection'] = domainselection

    if sitetype:
        payload['wisite']['sitetype'] = sitetype

    if userinterfacebranding:
        payload['wisite']['userinterfacebranding'] = userinterfacebranding

    if publishedresourcetype:
        payload['wisite']['publishedresourcetype'] = publishedresourcetype

    if kioskmode:
        payload['wisite']['kioskmode'] = kioskmode

    if showsearch:
        payload['wisite']['showsearch'] = showsearch

    if showrefresh:
        payload['wisite']['showrefresh'] = showrefresh

    if wiuserinterfacemodes:
        payload['wisite']['wiuserinterfacemodes'] = wiuserinterfacemodes

    if userinterfacelayouts:
        payload['wisite']['userinterfacelayouts'] = userinterfacelayouts

    if restrictdomains:
        payload['wisite']['restrictdomains'] = restrictdomains

    if logindomains:
        payload['wisite']['logindomains'] = logindomains

    if hidedomainfield:
        payload['wisite']['hidedomainfield'] = hidedomainfield

    if agcallbackurl:
        payload['wisite']['agcallbackurl'] = agcallbackurl

    execution = __proxy__['citrixns.post']('config/wisite', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_wisite_accessmethod_binding(clientipaddress=None, clientnetmask=None, accessmethod=None, sitepath=None,
                                    save=False):
    '''
    Add a new wisite_accessmethod_binding to the running configuration.

    clientipaddress(str): IPv4 or network address of the client for which you want to associate an access method. Default
        value: 0

    clientnetmask(str): Subnet mask associated with the IPv4 or network address specified by the Client IP Address parameter.
        Default value: 0

    accessmethod(str): Secure access method to be applied to the IPv4 or network address of the client specified by the
        Client IP Address parameter. Depending on whether the Web Interface site is configured to use an HTTP or HTTPS
        virtual server or to use access gateway, you can send clients or access gateway the IP address, or the alternate
        address, of a XenApp or XenDesktop server. Or, you can send the IP address translated from a mapping entry, which
        defines mapping of an internal address and port to an external address and port. Possible values = Direct,
        Alternate, Translated, GatewayDirect, GatewayAlternate, GatewayTranslated

    sitepath(str): Path to the Web Interface site. Minimum length = 1 Maximum length = 250

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.add_wisite_accessmethod_binding <args>

    '''

    result = {}

    payload = {'wisite_accessmethod_binding': {}}

    if clientipaddress:
        payload['wisite_accessmethod_binding']['clientipaddress'] = clientipaddress

    if clientnetmask:
        payload['wisite_accessmethod_binding']['clientnetmask'] = clientnetmask

    if accessmethod:
        payload['wisite_accessmethod_binding']['accessmethod'] = accessmethod

    if sitepath:
        payload['wisite_accessmethod_binding']['sitepath'] = sitepath

    execution = __proxy__['citrixns.post']('config/wisite_accessmethod_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_wisite_farmname_binding(sitepath=None, groups=None, xmlport=None, transport=None, sslrelayport=None,
                                farmname=None, save=False):
    '''
    Add a new wisite_farmname_binding to the running configuration.

    sitepath(str): Path to the Web Interface site. Minimum length = 1 Maximum length = 250

    groups(str): Active Directory groups that are permitted to enumerate resources from server farms. Including a setting for
        this parameter activates the user roaming feature. A maximum of 512 user groups can be specified for each farm
        defined with the Farm;lt;n;gt; parameter. The groups must be comma separated.

    xmlport(int): Port number at which to contact the XML service.

    transport(str): Transport protocol to use for transferring data, related to the Web Interface site, between the NetScaler
        appliance and the XML service. Possible values = HTTP, HTTPS, SSLRELAY

    sslrelayport(int): TCP port at which the XenApp or XenDesktop servers listenfor SSL Relay traffic from the NetScaler
        appliance. This parameter is required if you have set SSL Relay as the transport protocol. Web Interface uses
        root certificates when authenticating a server running SSL Relay. Make sure that all the servers running SSL
        Relay are configured to listen on the same port.

    farmname(str): Name for the logical representation of a XenApp or XenDesktop farm to be bound to the Web Interface site.
        Must begin with an ASCII alphabetic or underscore (

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.add_wisite_farmname_binding <args>

    '''

    result = {}

    payload = {'wisite_farmname_binding': {}}

    if sitepath:
        payload['wisite_farmname_binding']['sitepath'] = sitepath

    if groups:
        payload['wisite_farmname_binding']['groups'] = groups

    if xmlport:
        payload['wisite_farmname_binding']['xmlport'] = xmlport

    if transport:
        payload['wisite_farmname_binding']['transport'] = transport

    if sslrelayport:
        payload['wisite_farmname_binding']['sslrelayport'] = sslrelayport

    if farmname:
        payload['wisite_farmname_binding']['farmname'] = farmname

    execution = __proxy__['citrixns.post']('config/wisite_farmname_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_wisite_translationinternalip_binding(sitepath=None, accesstype=None, translationexternalport=None,
                                             translationinternalip=None, translationexternalip=None,
                                             translationinternalport=None, save=False):
    '''
    Add a new wisite_translationinternalip_binding to the running configuration.

    sitepath(str): Path to the Web Interface site. Minimum length = 1 Maximum length = 250

    accesstype(str): Type of access to the XenApp or XenDesktop server. Available settings function as follows: * User Device
        - Clients can use the translated address of the mapping entry to connect to the XenApp or XenDesktop server. *
        Gateway - Access Gateway can use the translated address of the mapping entry to connect to the XenApp or
        XenDesktop server. * User Device and Gateway - Both clients and Access Gateway can use the translated address of
        the mapping entry to connect to the XenApp or XenDesktop server. Default value: UserDevice Possible values =
        UserDevice, Gateway, UserDeviceAndGateway

    translationexternalport(int): External port number associated with the servers port number. Range 1 - 65535 * in CLI is
        represented as 65535 in NITRO API

    translationinternalip(str): IP address of the server for which you want to associate an external IP address. (Clients
        access the server through the associated external address and port.). Default value: 0

    translationexternalip(str): External IP address associated with servers IP address.

    translationinternalport(int): Port number of the server for which you want to associate an external port. (Clients access
        the server through the associated external address and port.). Range 1 - 65535 * in CLI is represented as 65535
        in NITRO API

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.add_wisite_translationinternalip_binding <args>

    '''

    result = {}

    payload = {'wisite_translationinternalip_binding': {}}

    if sitepath:
        payload['wisite_translationinternalip_binding']['sitepath'] = sitepath

    if accesstype:
        payload['wisite_translationinternalip_binding']['accesstype'] = accesstype

    if translationexternalport:
        payload['wisite_translationinternalip_binding']['translationexternalport'] = translationexternalport

    if translationinternalip:
        payload['wisite_translationinternalip_binding']['translationinternalip'] = translationinternalip

    if translationexternalip:
        payload['wisite_translationinternalip_binding']['translationexternalip'] = translationexternalip

    if translationinternalport:
        payload['wisite_translationinternalip_binding']['translationinternalport'] = translationinternalport

    execution = __proxy__['citrixns.post']('config/wisite_translationinternalip_binding', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_wipackage():
    '''
    Show the running configuration for the wipackage config key.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.get_wipackage

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wipackage'), 'wipackage')

    return response


def get_wisite(sitepath=None, agurl=None, staurl=None, secondstaurl=None, sessionreliability=None, usetwotickets=None,
               authenticationpoint=None, agauthenticationmethod=None, wiauthenticationmethods=None,
               defaultcustomtextlocale=None, websessiontimeout=None, defaultaccessmethod=None, logintitle=None,
               appwelcomemessage=None, welcomemessage=None, footertext=None, loginsysmessage=None, preloginbutton=None,
               preloginmessage=None, prelogintitle=None, domainselection=None, sitetype=None, userinterfacebranding=None,
               publishedresourcetype=None, kioskmode=None, showsearch=None, showrefresh=None, wiuserinterfacemodes=None,
               userinterfacelayouts=None, restrictdomains=None, logindomains=None, hidedomainfield=None,
               agcallbackurl=None):
    '''
    Show the running configuration for the wisite config key.

    sitepath(str): Filters results that only match the sitepath field.

    agurl(str): Filters results that only match the agurl field.

    staurl(str): Filters results that only match the staurl field.

    secondstaurl(str): Filters results that only match the secondstaurl field.

    sessionreliability(str): Filters results that only match the sessionreliability field.

    usetwotickets(str): Filters results that only match the usetwotickets field.

    authenticationpoint(str): Filters results that only match the authenticationpoint field.

    agauthenticationmethod(str): Filters results that only match the agauthenticationmethod field.

    wiauthenticationmethods(list(str)): Filters results that only match the wiauthenticationmethods field.

    defaultcustomtextlocale(str): Filters results that only match the defaultcustomtextlocale field.

    websessiontimeout(int): Filters results that only match the websessiontimeout field.

    defaultaccessmethod(str): Filters results that only match the defaultaccessmethod field.

    logintitle(str): Filters results that only match the logintitle field.

    appwelcomemessage(str): Filters results that only match the appwelcomemessage field.

    welcomemessage(str): Filters results that only match the welcomemessage field.

    footertext(str): Filters results that only match the footertext field.

    loginsysmessage(str): Filters results that only match the loginsysmessage field.

    preloginbutton(str): Filters results that only match the preloginbutton field.

    preloginmessage(str): Filters results that only match the preloginmessage field.

    prelogintitle(str): Filters results that only match the prelogintitle field.

    domainselection(str): Filters results that only match the domainselection field.

    sitetype(str): Filters results that only match the sitetype field.

    userinterfacebranding(str): Filters results that only match the userinterfacebranding field.

    publishedresourcetype(str): Filters results that only match the publishedresourcetype field.

    kioskmode(str): Filters results that only match the kioskmode field.

    showsearch(str): Filters results that only match the showsearch field.

    showrefresh(str): Filters results that only match the showrefresh field.

    wiuserinterfacemodes(str): Filters results that only match the wiuserinterfacemodes field.

    userinterfacelayouts(str): Filters results that only match the userinterfacelayouts field.

    restrictdomains(str): Filters results that only match the restrictdomains field.

    logindomains(str): Filters results that only match the logindomains field.

    hidedomainfield(str): Filters results that only match the hidedomainfield field.

    agcallbackurl(str): Filters results that only match the agcallbackurl field.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.get_wisite

    '''

    search_filter = []

    if sitepath:
        search_filter.append(['sitepath', sitepath])

    if agurl:
        search_filter.append(['agurl', agurl])

    if staurl:
        search_filter.append(['staurl', staurl])

    if secondstaurl:
        search_filter.append(['secondstaurl', secondstaurl])

    if sessionreliability:
        search_filter.append(['sessionreliability', sessionreliability])

    if usetwotickets:
        search_filter.append(['usetwotickets', usetwotickets])

    if authenticationpoint:
        search_filter.append(['authenticationpoint', authenticationpoint])

    if agauthenticationmethod:
        search_filter.append(['agauthenticationmethod', agauthenticationmethod])

    if wiauthenticationmethods:
        search_filter.append(['wiauthenticationmethods', wiauthenticationmethods])

    if defaultcustomtextlocale:
        search_filter.append(['defaultcustomtextlocale', defaultcustomtextlocale])

    if websessiontimeout:
        search_filter.append(['websessiontimeout', websessiontimeout])

    if defaultaccessmethod:
        search_filter.append(['defaultaccessmethod', defaultaccessmethod])

    if logintitle:
        search_filter.append(['logintitle', logintitle])

    if appwelcomemessage:
        search_filter.append(['appwelcomemessage', appwelcomemessage])

    if welcomemessage:
        search_filter.append(['welcomemessage', welcomemessage])

    if footertext:
        search_filter.append(['footertext', footertext])

    if loginsysmessage:
        search_filter.append(['loginsysmessage', loginsysmessage])

    if preloginbutton:
        search_filter.append(['preloginbutton', preloginbutton])

    if preloginmessage:
        search_filter.append(['preloginmessage', preloginmessage])

    if prelogintitle:
        search_filter.append(['prelogintitle', prelogintitle])

    if domainselection:
        search_filter.append(['domainselection', domainselection])

    if sitetype:
        search_filter.append(['sitetype', sitetype])

    if userinterfacebranding:
        search_filter.append(['userinterfacebranding', userinterfacebranding])

    if publishedresourcetype:
        search_filter.append(['publishedresourcetype', publishedresourcetype])

    if kioskmode:
        search_filter.append(['kioskmode', kioskmode])

    if showsearch:
        search_filter.append(['showsearch', showsearch])

    if showrefresh:
        search_filter.append(['showrefresh', showrefresh])

    if wiuserinterfacemodes:
        search_filter.append(['wiuserinterfacemodes', wiuserinterfacemodes])

    if userinterfacelayouts:
        search_filter.append(['userinterfacelayouts', userinterfacelayouts])

    if restrictdomains:
        search_filter.append(['restrictdomains', restrictdomains])

    if logindomains:
        search_filter.append(['logindomains', logindomains])

    if hidedomainfield:
        search_filter.append(['hidedomainfield', hidedomainfield])

    if agcallbackurl:
        search_filter.append(['agcallbackurl', agcallbackurl])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wisite{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'wisite')

    return response


def get_wisite_accessmethod_binding(clientipaddress=None, clientnetmask=None, accessmethod=None, sitepath=None):
    '''
    Show the running configuration for the wisite_accessmethod_binding config key.

    clientipaddress(str): Filters results that only match the clientipaddress field.

    clientnetmask(str): Filters results that only match the clientnetmask field.

    accessmethod(str): Filters results that only match the accessmethod field.

    sitepath(str): Filters results that only match the sitepath field.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.get_wisite_accessmethod_binding

    '''

    search_filter = []

    if clientipaddress:
        search_filter.append(['clientipaddress', clientipaddress])

    if clientnetmask:
        search_filter.append(['clientnetmask', clientnetmask])

    if accessmethod:
        search_filter.append(['accessmethod', accessmethod])

    if sitepath:
        search_filter.append(['sitepath', sitepath])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wisite_accessmethod_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'wisite_accessmethod_binding')

    return response


def get_wisite_binding():
    '''
    Show the running configuration for the wisite_binding config key.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.get_wisite_binding

    '''

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wisite_binding'), 'wisite_binding')

    return response


def get_wisite_farmname_binding(sitepath=None, groups=None, xmlport=None, transport=None, sslrelayport=None,
                                farmname=None):
    '''
    Show the running configuration for the wisite_farmname_binding config key.

    sitepath(str): Filters results that only match the sitepath field.

    groups(str): Filters results that only match the groups field.

    xmlport(int): Filters results that only match the xmlport field.

    transport(str): Filters results that only match the transport field.

    sslrelayport(int): Filters results that only match the sslrelayport field.

    farmname(str): Filters results that only match the farmname field.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.get_wisite_farmname_binding

    '''

    search_filter = []

    if sitepath:
        search_filter.append(['sitepath', sitepath])

    if groups:
        search_filter.append(['groups', groups])

    if xmlport:
        search_filter.append(['xmlport', xmlport])

    if transport:
        search_filter.append(['transport', transport])

    if sslrelayport:
        search_filter.append(['sslrelayport', sslrelayport])

    if farmname:
        search_filter.append(['farmname', farmname])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wisite_farmname_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'wisite_farmname_binding')

    return response


def get_wisite_translationinternalip_binding(sitepath=None, accesstype=None, translationexternalport=None,
                                             translationinternalip=None, translationexternalip=None,
                                             translationinternalport=None):
    '''
    Show the running configuration for the wisite_translationinternalip_binding config key.

    sitepath(str): Filters results that only match the sitepath field.

    accesstype(str): Filters results that only match the accesstype field.

    translationexternalport(int): Filters results that only match the translationexternalport field.

    translationinternalip(str): Filters results that only match the translationinternalip field.

    translationexternalip(str): Filters results that only match the translationexternalip field.

    translationinternalport(int): Filters results that only match the translationinternalport field.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.get_wisite_translationinternalip_binding

    '''

    search_filter = []

    if sitepath:
        search_filter.append(['sitepath', sitepath])

    if accesstype:
        search_filter.append(['accesstype', accesstype])

    if translationexternalport:
        search_filter.append(['translationexternalport', translationexternalport])

    if translationinternalip:
        search_filter.append(['translationinternalip', translationinternalip])

    if translationexternalip:
        search_filter.append(['translationexternalip', translationexternalip])

    if translationinternalport:
        search_filter.append(['translationinternalport', translationinternalport])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/wisite_translationinternalip_binding{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'wisite_translationinternalip_binding')

    return response


def unset_wisite(sitepath=None, agurl=None, staurl=None, secondstaurl=None, sessionreliability=None, usetwotickets=None,
                 authenticationpoint=None, agauthenticationmethod=None, wiauthenticationmethods=None,
                 defaultcustomtextlocale=None, websessiontimeout=None, defaultaccessmethod=None, logintitle=None,
                 appwelcomemessage=None, welcomemessage=None, footertext=None, loginsysmessage=None, preloginbutton=None,
                 preloginmessage=None, prelogintitle=None, domainselection=None, sitetype=None,
                 userinterfacebranding=None, publishedresourcetype=None, kioskmode=None, showsearch=None,
                 showrefresh=None, wiuserinterfacemodes=None, userinterfacelayouts=None, restrictdomains=None,
                 logindomains=None, hidedomainfield=None, agcallbackurl=None, save=False):
    '''
    Unsets values from the wisite configuration key.

    sitepath(bool): Unsets the sitepath value.

    agurl(bool): Unsets the agurl value.

    staurl(bool): Unsets the staurl value.

    secondstaurl(bool): Unsets the secondstaurl value.

    sessionreliability(bool): Unsets the sessionreliability value.

    usetwotickets(bool): Unsets the usetwotickets value.

    authenticationpoint(bool): Unsets the authenticationpoint value.

    agauthenticationmethod(bool): Unsets the agauthenticationmethod value.

    wiauthenticationmethods(bool): Unsets the wiauthenticationmethods value.

    defaultcustomtextlocale(bool): Unsets the defaultcustomtextlocale value.

    websessiontimeout(bool): Unsets the websessiontimeout value.

    defaultaccessmethod(bool): Unsets the defaultaccessmethod value.

    logintitle(bool): Unsets the logintitle value.

    appwelcomemessage(bool): Unsets the appwelcomemessage value.

    welcomemessage(bool): Unsets the welcomemessage value.

    footertext(bool): Unsets the footertext value.

    loginsysmessage(bool): Unsets the loginsysmessage value.

    preloginbutton(bool): Unsets the preloginbutton value.

    preloginmessage(bool): Unsets the preloginmessage value.

    prelogintitle(bool): Unsets the prelogintitle value.

    domainselection(bool): Unsets the domainselection value.

    sitetype(bool): Unsets the sitetype value.

    userinterfacebranding(bool): Unsets the userinterfacebranding value.

    publishedresourcetype(bool): Unsets the publishedresourcetype value.

    kioskmode(bool): Unsets the kioskmode value.

    showsearch(bool): Unsets the showsearch value.

    showrefresh(bool): Unsets the showrefresh value.

    wiuserinterfacemodes(bool): Unsets the wiuserinterfacemodes value.

    userinterfacelayouts(bool): Unsets the userinterfacelayouts value.

    restrictdomains(bool): Unsets the restrictdomains value.

    logindomains(bool): Unsets the logindomains value.

    hidedomainfield(bool): Unsets the hidedomainfield value.

    agcallbackurl(bool): Unsets the agcallbackurl value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.unset_wisite <args>

    '''

    result = {}

    payload = {'wisite': {}}

    if sitepath:
        payload['wisite']['sitepath'] = True

    if agurl:
        payload['wisite']['agurl'] = True

    if staurl:
        payload['wisite']['staurl'] = True

    if secondstaurl:
        payload['wisite']['secondstaurl'] = True

    if sessionreliability:
        payload['wisite']['sessionreliability'] = True

    if usetwotickets:
        payload['wisite']['usetwotickets'] = True

    if authenticationpoint:
        payload['wisite']['authenticationpoint'] = True

    if agauthenticationmethod:
        payload['wisite']['agauthenticationmethod'] = True

    if wiauthenticationmethods:
        payload['wisite']['wiauthenticationmethods'] = True

    if defaultcustomtextlocale:
        payload['wisite']['defaultcustomtextlocale'] = True

    if websessiontimeout:
        payload['wisite']['websessiontimeout'] = True

    if defaultaccessmethod:
        payload['wisite']['defaultaccessmethod'] = True

    if logintitle:
        payload['wisite']['logintitle'] = True

    if appwelcomemessage:
        payload['wisite']['appwelcomemessage'] = True

    if welcomemessage:
        payload['wisite']['welcomemessage'] = True

    if footertext:
        payload['wisite']['footertext'] = True

    if loginsysmessage:
        payload['wisite']['loginsysmessage'] = True

    if preloginbutton:
        payload['wisite']['preloginbutton'] = True

    if preloginmessage:
        payload['wisite']['preloginmessage'] = True

    if prelogintitle:
        payload['wisite']['prelogintitle'] = True

    if domainselection:
        payload['wisite']['domainselection'] = True

    if sitetype:
        payload['wisite']['sitetype'] = True

    if userinterfacebranding:
        payload['wisite']['userinterfacebranding'] = True

    if publishedresourcetype:
        payload['wisite']['publishedresourcetype'] = True

    if kioskmode:
        payload['wisite']['kioskmode'] = True

    if showsearch:
        payload['wisite']['showsearch'] = True

    if showrefresh:
        payload['wisite']['showrefresh'] = True

    if wiuserinterfacemodes:
        payload['wisite']['wiuserinterfacemodes'] = True

    if userinterfacelayouts:
        payload['wisite']['userinterfacelayouts'] = True

    if restrictdomains:
        payload['wisite']['restrictdomains'] = True

    if logindomains:
        payload['wisite']['logindomains'] = True

    if hidedomainfield:
        payload['wisite']['hidedomainfield'] = True

    if agcallbackurl:
        payload['wisite']['agcallbackurl'] = True

    execution = __proxy__['citrixns.post']('config/wisite?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_wisite(sitepath=None, agurl=None, staurl=None, secondstaurl=None, sessionreliability=None, usetwotickets=None,
                  authenticationpoint=None, agauthenticationmethod=None, wiauthenticationmethods=None,
                  defaultcustomtextlocale=None, websessiontimeout=None, defaultaccessmethod=None, logintitle=None,
                  appwelcomemessage=None, welcomemessage=None, footertext=None, loginsysmessage=None,
                  preloginbutton=None, preloginmessage=None, prelogintitle=None, domainselection=None, sitetype=None,
                  userinterfacebranding=None, publishedresourcetype=None, kioskmode=None, showsearch=None,
                  showrefresh=None, wiuserinterfacemodes=None, userinterfacelayouts=None, restrictdomains=None,
                  logindomains=None, hidedomainfield=None, agcallbackurl=None, save=False):
    '''
    Update the running configuration for the wisite config key.

    sitepath(str): Path to the Web Interface site being created on the NetScaler appliance. Minimum length = 1 Maximum length
        = 250

    agurl(str): Call back URL of the Gateway. Minimum length = 1 Maximum length = 255

    staurl(str): URL of the Secure Ticket Authority (STA) server. Minimum length = 1 Maximum length = 255

    secondstaurl(str): URL of the second Secure Ticket Authority (STA) server. Minimum length = 1 Maximum length = 255

    sessionreliability(str): Enable session reliability through Access Gateway. Default value: OFF Possible values = ON, OFF

    usetwotickets(str): Request tickets issued by two separate Secure Ticket Authorities (STA) when a resource is accessed.
        Default value: OFF Possible values = ON, OFF

    authenticationpoint(str): Authentication point for the Web Interface site. Possible values = WebInterface, AccessGateway

    agauthenticationmethod(str): Method for authenticating a Web Interface site if you have specified Web Interface as the
        authentication point.  Available settings function as follows:  * Explicit - Users must provide a user name and
        password to log on to the Web Interface.  * Anonymous - Users can log on to the Web Interface without providing a
        user name and password. They have access to resources published for anonymous users. Possible values = Explicit,
        SmartCard

    wiauthenticationmethods(list(str)): The method of authentication to be used at Web Interface. Default value: Explicit
        Possible values = Explicit, Anonymous

    defaultcustomtextlocale(str): Default language for the Web Interface site. Default value: English Possible values =
        German, English, Spanish, French, Japanese, Korean, Russian, Chinese_simplified, Chinese_traditional

    websessiontimeout(int): Time-out, in minutes, for idle Web Interface browser sessions. If a clients session is idle for a
        time that exceeds the time-out value, the NetScaler appliance terminates the connection. Default value: 20
        Minimum value = 1 Maximum value = 1440

    defaultaccessmethod(str): Default access method for clients accessing the Web Interface site.    Note: Before you
        configure an access method based on the client IP address, you must enable USIP mode on the Web Interface service
        to make the clients IP address available with the Web Interface.  Depending on whether the Web Interface site is
        configured to use an HTTP or HTTPS virtual server or to use access gateway, you can send clients or access
        gateway the IP address, or the alternate address, of a XenApp or XenDesktop server. Or, you can send the IP
        address translated from a mapping entry, which defines mapping of an internal address and port to an external
        address and port.  Note: In the NetScaler command line, mapping entries can be created by using the bind wi site
        command. Possible values = Direct, Alternate, Translated, GatewayDirect, GatewayAlternate, GatewayTranslated

    logintitle(str): A custom login page title for the Web Interface site. Default value: "Welcome to Web Interface on
        NetScaler" Minimum length = 1 Maximum length = 255

    appwelcomemessage(str): Specifies localized text to appear at the top of the main content area of the Applications
        screen. LanguageCode is en, de, es, fr, ja, or any other supported language identifier. Minimum length = 1
        Maximum length = 255

    welcomemessage(str): Localized welcome message that appears on the welcome area of the login screen. Minimum length = 1
        Maximum length = 255

    footertext(str): Localized text that appears in the footer area of all pages. Minimum length = 1 Maximum length = 255

    loginsysmessage(str): Localized text that appears at the bottom of the main content area of the login screen. Minimum
        length = 1 Maximum length = 255

    preloginbutton(str): Localized text that appears as the name of the pre-login message confirmation button. Minimum length
        = 1 Maximum length = 255

    preloginmessage(str): Localized text that appears on the pre-login message page. Minimum length = 1 Maximum length =
        2048

    prelogintitle(str): Localized text that appears as the title of the pre-login message page. Minimum length = 1 Maximum
        length = 255

    domainselection(str): Domain names listed on the login screen for explicit authentication. Minimum length = 1 Maximum
        length = 255

    sitetype(str): Type of access to the Web Interface site. Available settings function as follows: * XenApp/XenDesktop web
        site - Configures the Web Interface site for access by a web browser. * XenApp/XenDesktop services site -
        Configures the Web Interface site for access by the XenApp plug-in. Default value: XenAppWeb Possible values =
        XenAppWeb, XenAppServices

    userinterfacebranding(str): Specifies whether the site is focused towards users accessing applications or desktops.
        Setting the parameter to Desktops changes the functionality of the site to improve the experience for XenDesktop
        users. Citrix recommends using this setting for any deployment that includes XenDesktop. Default value:
        Applications Possible values = Desktops, Applications

    publishedresourcetype(str): Method for accessing the published XenApp and XenDesktop resources.   Available settings
        function as follows:  * Online - Allows applications to be launched on the XenApp and XenDesktop servers.   *
        Offline - Allows streaming of applications to the client.   * DualMode - Allows both online and offline modes.
        Default value: Online Possible values = Online, Offline, DualMode

    kioskmode(str): User settings do not persist from one session to another. Default value: OFF Possible values = ON, OFF

    showsearch(str): Enables search option on XenApp websites. Default value: OFF Possible values = ON, OFF

    showrefresh(str): Provides the Refresh button on the applications screen. Default value: OFF Possible values = ON, OFF

    wiuserinterfacemodes(str): Appearance of the login screen.  * Simple - Only the login fields for the selected
        authentication method are displayed.  * Advanced - Displays the navigation bar, which provides access to the
        pre-login messages and preferences screens. Default value: SIMPLE Possible values = SIMPLE, ADVANCED

    userinterfacelayouts(str): Specifies whether or not to use the compact user interface. Default value: AUTO Possible
        values = AUTO, NORMAL, COMPACT

    restrictdomains(str): The RestrictDomains setting is used to enable/disable domain restrictions. If domain restriction is
        enabled, the LoginDomains list is used for validating the login domain. It is applied to all the authentication
        methods except Anonymous for XenApp Web and XenApp Services sites. Default value: OFF Possible values = ON, OFF

    logindomains(str): [List of NetBIOS domain names], Domain names to use for access restriction.  Only takes effect when
        used in conjunction with the RestrictDomains setting. Minimum length = 1 Maximum length = 255

    hidedomainfield(str): The HideDomainField setting is used to control whether the domain field is displayed on the logon
        screen. Default value: OFF Possible values = ON, OFF

    agcallbackurl(str): Callback AGURL to which Web Interface contacts. . Minimum length = 1 Maximum length = 255

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' webinterface.update_wisite <args>

    '''

    result = {}

    payload = {'wisite': {}}

    if sitepath:
        payload['wisite']['sitepath'] = sitepath

    if agurl:
        payload['wisite']['agurl'] = agurl

    if staurl:
        payload['wisite']['staurl'] = staurl

    if secondstaurl:
        payload['wisite']['secondstaurl'] = secondstaurl

    if sessionreliability:
        payload['wisite']['sessionreliability'] = sessionreliability

    if usetwotickets:
        payload['wisite']['usetwotickets'] = usetwotickets

    if authenticationpoint:
        payload['wisite']['authenticationpoint'] = authenticationpoint

    if agauthenticationmethod:
        payload['wisite']['agauthenticationmethod'] = agauthenticationmethod

    if wiauthenticationmethods:
        payload['wisite']['wiauthenticationmethods'] = wiauthenticationmethods

    if defaultcustomtextlocale:
        payload['wisite']['defaultcustomtextlocale'] = defaultcustomtextlocale

    if websessiontimeout:
        payload['wisite']['websessiontimeout'] = websessiontimeout

    if defaultaccessmethod:
        payload['wisite']['defaultaccessmethod'] = defaultaccessmethod

    if logintitle:
        payload['wisite']['logintitle'] = logintitle

    if appwelcomemessage:
        payload['wisite']['appwelcomemessage'] = appwelcomemessage

    if welcomemessage:
        payload['wisite']['welcomemessage'] = welcomemessage

    if footertext:
        payload['wisite']['footertext'] = footertext

    if loginsysmessage:
        payload['wisite']['loginsysmessage'] = loginsysmessage

    if preloginbutton:
        payload['wisite']['preloginbutton'] = preloginbutton

    if preloginmessage:
        payload['wisite']['preloginmessage'] = preloginmessage

    if prelogintitle:
        payload['wisite']['prelogintitle'] = prelogintitle

    if domainselection:
        payload['wisite']['domainselection'] = domainselection

    if sitetype:
        payload['wisite']['sitetype'] = sitetype

    if userinterfacebranding:
        payload['wisite']['userinterfacebranding'] = userinterfacebranding

    if publishedresourcetype:
        payload['wisite']['publishedresourcetype'] = publishedresourcetype

    if kioskmode:
        payload['wisite']['kioskmode'] = kioskmode

    if showsearch:
        payload['wisite']['showsearch'] = showsearch

    if showrefresh:
        payload['wisite']['showrefresh'] = showrefresh

    if wiuserinterfacemodes:
        payload['wisite']['wiuserinterfacemodes'] = wiuserinterfacemodes

    if userinterfacelayouts:
        payload['wisite']['userinterfacelayouts'] = userinterfacelayouts

    if restrictdomains:
        payload['wisite']['restrictdomains'] = restrictdomains

    if logindomains:
        payload['wisite']['logindomains'] = logindomains

    if hidedomainfield:
        payload['wisite']['hidedomainfield'] = hidedomainfield

    if agcallbackurl:
        payload['wisite']['agcallbackurl'] = agcallbackurl

    execution = __proxy__['citrixns.put']('config/wisite', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
