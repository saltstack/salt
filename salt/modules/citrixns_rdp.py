# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the rdp key.

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

__virtualname__ = 'rdp'


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

    return False, 'The rdp execution module can only be loaded for citrixns proxy minions.'


def add_rdpclientprofile(name=None, rdpurloverride=None, redirectclipboard=None, redirectdrives=None,
                         redirectprinters=None, redirectcomports=None, redirectpnpdevices=None, keyboardhook=None,
                         audiocapturemode=None, videoplaybackmode=None, multimonitorsupport=None, rdpcookievalidity=None,
                         addusernameinrdpfile=None, rdpfilename=None, rdphost=None, rdplistener=None,
                         rdpcustomparams=None, psk=None, save=False):
    '''
    Add a new rdpclientprofile to the running configuration.

    name(str): The name of the rdp profile. Minimum length = 1

    rdpurloverride(str): This setting determines whether the RDP parameters supplied in the vpn url override those specified
        in the RDP profile. Default value: ENABLE Possible values = ENABLE, DISABLE

    redirectclipboard(str): This setting corresponds to the Clipboard check box on the Local Resources tab under Options in
        RDC. Default value: ENABLE Possible values = ENABLE, DISABLE

    redirectdrives(str): This setting corresponds to the selections for Drives under More on the Local Resources tab under
        Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    redirectprinters(str): This setting corresponds to the selection in the Printers check box on the Local Resources tab
        under Options in RDC. Default value: ENABLE Possible values = ENABLE, DISABLE

    redirectcomports(str): This setting corresponds to the selections for comports under More on the Local Resources tab
        under Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    redirectpnpdevices(str): This setting corresponds to the selections for pnpdevices under More on the Local Resources tab
        under Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    keyboardhook(str): This setting corresponds to the selection in the Keyboard drop-down list on the Local Resources tab
        under Options in RDC. Default value: InFullScreenMode Possible values = OnLocal, OnRemote, InFullScreenMode

    audiocapturemode(str): This setting corresponds to the selections in the Remote audio area on the Local Resources tab
        under Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    videoplaybackmode(str): This setting determines if Remote Desktop Connection (RDC) will use RDP efficient multimedia
        streaming for video playback. Default value: ENABLE Possible values = ENABLE, DISABLE

    multimonitorsupport(str): Enable/Disable Multiple Monitor Support for Remote Desktop Connection (RDC). Default value:
        ENABLE Possible values = ENABLE, DISABLE

    rdpcookievalidity(int): RDP cookie validity period. Default value: 60 Minimum value = 60 Maximum value = 86400

    addusernameinrdpfile(str): Add username in rdp file. Default value: NO Possible values = YES, NO

    rdpfilename(str): RDP file name to be sent to End User. Minimum length = 1

    rdphost(str): Fully-qualified domain name (FQDN) of the RDP Listener. Maximum length = 252

    rdplistener(str): Fully-qualified domain name (FQDN) of the RDP Listener with the port in the format FQDN:Port. Maximum
        length = 258

    rdpcustomparams(str): Option for RDP custom parameters settings (if any). Custom params needs to be separated by ;amp;.
        Default value: 0 Minimum length = 1

    psk(str): Pre shared key value. Default value: 0

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.add_rdpclientprofile <args>

    '''

    result = {}

    payload = {'rdpclientprofile': {}}

    if name:
        payload['rdpclientprofile']['name'] = name

    if rdpurloverride:
        payload['rdpclientprofile']['rdpurloverride'] = rdpurloverride

    if redirectclipboard:
        payload['rdpclientprofile']['redirectclipboard'] = redirectclipboard

    if redirectdrives:
        payload['rdpclientprofile']['redirectdrives'] = redirectdrives

    if redirectprinters:
        payload['rdpclientprofile']['redirectprinters'] = redirectprinters

    if redirectcomports:
        payload['rdpclientprofile']['redirectcomports'] = redirectcomports

    if redirectpnpdevices:
        payload['rdpclientprofile']['redirectpnpdevices'] = redirectpnpdevices

    if keyboardhook:
        payload['rdpclientprofile']['keyboardhook'] = keyboardhook

    if audiocapturemode:
        payload['rdpclientprofile']['audiocapturemode'] = audiocapturemode

    if videoplaybackmode:
        payload['rdpclientprofile']['videoplaybackmode'] = videoplaybackmode

    if multimonitorsupport:
        payload['rdpclientprofile']['multimonitorsupport'] = multimonitorsupport

    if rdpcookievalidity:
        payload['rdpclientprofile']['rdpcookievalidity'] = rdpcookievalidity

    if addusernameinrdpfile:
        payload['rdpclientprofile']['addusernameinrdpfile'] = addusernameinrdpfile

    if rdpfilename:
        payload['rdpclientprofile']['rdpfilename'] = rdpfilename

    if rdphost:
        payload['rdpclientprofile']['rdphost'] = rdphost

    if rdplistener:
        payload['rdpclientprofile']['rdplistener'] = rdplistener

    if rdpcustomparams:
        payload['rdpclientprofile']['rdpcustomparams'] = rdpcustomparams

    if psk:
        payload['rdpclientprofile']['psk'] = psk

    execution = __proxy__['citrixns.post']('config/rdpclientprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def add_rdpserverprofile(name=None, rdpip=None, rdpport=None, psk=None, save=False):
    '''
    Add a new rdpserverprofile to the running configuration.

    name(str): The name of the rdp server profile. Minimum length = 1 Maximum length = 32

    rdpip(str): IPv4 or IPv6 address of RDP listener. This terminates client RDP connections. Minimum length = 1

    rdpport(int): TCP port on which the RDP connection is established. Default value: 3389 Minimum value = 1 Maximum value =
        65535

    psk(str): Pre shared key value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.add_rdpserverprofile <args>

    '''

    result = {}

    payload = {'rdpserverprofile': {}}

    if name:
        payload['rdpserverprofile']['name'] = name

    if rdpip:
        payload['rdpserverprofile']['rdpip'] = rdpip

    if rdpport:
        payload['rdpserverprofile']['rdpport'] = rdpport

    if psk:
        payload['rdpserverprofile']['psk'] = psk

    execution = __proxy__['citrixns.post']('config/rdpserverprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def get_rdpclientprofile(name=None, rdpurloverride=None, redirectclipboard=None, redirectdrives=None,
                         redirectprinters=None, redirectcomports=None, redirectpnpdevices=None, keyboardhook=None,
                         audiocapturemode=None, videoplaybackmode=None, multimonitorsupport=None, rdpcookievalidity=None,
                         addusernameinrdpfile=None, rdpfilename=None, rdphost=None, rdplistener=None,
                         rdpcustomparams=None, psk=None):
    '''
    Show the running configuration for the rdpclientprofile config key.

    name(str): Filters results that only match the name field.

    rdpurloverride(str): Filters results that only match the rdpurloverride field.

    redirectclipboard(str): Filters results that only match the redirectclipboard field.

    redirectdrives(str): Filters results that only match the redirectdrives field.

    redirectprinters(str): Filters results that only match the redirectprinters field.

    redirectcomports(str): Filters results that only match the redirectcomports field.

    redirectpnpdevices(str): Filters results that only match the redirectpnpdevices field.

    keyboardhook(str): Filters results that only match the keyboardhook field.

    audiocapturemode(str): Filters results that only match the audiocapturemode field.

    videoplaybackmode(str): Filters results that only match the videoplaybackmode field.

    multimonitorsupport(str): Filters results that only match the multimonitorsupport field.

    rdpcookievalidity(int): Filters results that only match the rdpcookievalidity field.

    addusernameinrdpfile(str): Filters results that only match the addusernameinrdpfile field.

    rdpfilename(str): Filters results that only match the rdpfilename field.

    rdphost(str): Filters results that only match the rdphost field.

    rdplistener(str): Filters results that only match the rdplistener field.

    rdpcustomparams(str): Filters results that only match the rdpcustomparams field.

    psk(str): Filters results that only match the psk field.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.get_rdpclientprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rdpurloverride:
        search_filter.append(['rdpurloverride', rdpurloverride])

    if redirectclipboard:
        search_filter.append(['redirectclipboard', redirectclipboard])

    if redirectdrives:
        search_filter.append(['redirectdrives', redirectdrives])

    if redirectprinters:
        search_filter.append(['redirectprinters', redirectprinters])

    if redirectcomports:
        search_filter.append(['redirectcomports', redirectcomports])

    if redirectpnpdevices:
        search_filter.append(['redirectpnpdevices', redirectpnpdevices])

    if keyboardhook:
        search_filter.append(['keyboardhook', keyboardhook])

    if audiocapturemode:
        search_filter.append(['audiocapturemode', audiocapturemode])

    if videoplaybackmode:
        search_filter.append(['videoplaybackmode', videoplaybackmode])

    if multimonitorsupport:
        search_filter.append(['multimonitorsupport', multimonitorsupport])

    if rdpcookievalidity:
        search_filter.append(['rdpcookievalidity', rdpcookievalidity])

    if addusernameinrdpfile:
        search_filter.append(['addusernameinrdpfile', addusernameinrdpfile])

    if rdpfilename:
        search_filter.append(['rdpfilename', rdpfilename])

    if rdphost:
        search_filter.append(['rdphost', rdphost])

    if rdplistener:
        search_filter.append(['rdplistener', rdplistener])

    if rdpcustomparams:
        search_filter.append(['rdpcustomparams', rdpcustomparams])

    if psk:
        search_filter.append(['psk', psk])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rdpclientprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rdpclientprofile')

    return response


def get_rdpconnections(username=None):
    '''
    Show the running configuration for the rdpconnections config key.

    username(str): Filters results that only match the username field.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.get_rdpconnections

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rdpconnections{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rdpconnections')

    return response


def get_rdpserverprofile(name=None, rdpip=None, rdpport=None, psk=None):
    '''
    Show the running configuration for the rdpserverprofile config key.

    name(str): Filters results that only match the name field.

    rdpip(str): Filters results that only match the rdpip field.

    rdpport(int): Filters results that only match the rdpport field.

    psk(str): Filters results that only match the psk field.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.get_rdpserverprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if rdpip:
        search_filter.append(['rdpip', rdpip])

    if rdpport:
        search_filter.append(['rdpport', rdpport])

    if psk:
        search_filter.append(['psk', psk])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/rdpserverprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'rdpserverprofile')

    return response


def unset_rdpclientprofile(name=None, rdpurloverride=None, redirectclipboard=None, redirectdrives=None,
                           redirectprinters=None, redirectcomports=None, redirectpnpdevices=None, keyboardhook=None,
                           audiocapturemode=None, videoplaybackmode=None, multimonitorsupport=None,
                           rdpcookievalidity=None, addusernameinrdpfile=None, rdpfilename=None, rdphost=None,
                           rdplistener=None, rdpcustomparams=None, psk=None, save=False):
    '''
    Unsets values from the rdpclientprofile configuration key.

    name(bool): Unsets the name value.

    rdpurloverride(bool): Unsets the rdpurloverride value.

    redirectclipboard(bool): Unsets the redirectclipboard value.

    redirectdrives(bool): Unsets the redirectdrives value.

    redirectprinters(bool): Unsets the redirectprinters value.

    redirectcomports(bool): Unsets the redirectcomports value.

    redirectpnpdevices(bool): Unsets the redirectpnpdevices value.

    keyboardhook(bool): Unsets the keyboardhook value.

    audiocapturemode(bool): Unsets the audiocapturemode value.

    videoplaybackmode(bool): Unsets the videoplaybackmode value.

    multimonitorsupport(bool): Unsets the multimonitorsupport value.

    rdpcookievalidity(bool): Unsets the rdpcookievalidity value.

    addusernameinrdpfile(bool): Unsets the addusernameinrdpfile value.

    rdpfilename(bool): Unsets the rdpfilename value.

    rdphost(bool): Unsets the rdphost value.

    rdplistener(bool): Unsets the rdplistener value.

    rdpcustomparams(bool): Unsets the rdpcustomparams value.

    psk(bool): Unsets the psk value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.unset_rdpclientprofile <args>

    '''

    result = {}

    payload = {'rdpclientprofile': {}}

    if name:
        payload['rdpclientprofile']['name'] = True

    if rdpurloverride:
        payload['rdpclientprofile']['rdpurloverride'] = True

    if redirectclipboard:
        payload['rdpclientprofile']['redirectclipboard'] = True

    if redirectdrives:
        payload['rdpclientprofile']['redirectdrives'] = True

    if redirectprinters:
        payload['rdpclientprofile']['redirectprinters'] = True

    if redirectcomports:
        payload['rdpclientprofile']['redirectcomports'] = True

    if redirectpnpdevices:
        payload['rdpclientprofile']['redirectpnpdevices'] = True

    if keyboardhook:
        payload['rdpclientprofile']['keyboardhook'] = True

    if audiocapturemode:
        payload['rdpclientprofile']['audiocapturemode'] = True

    if videoplaybackmode:
        payload['rdpclientprofile']['videoplaybackmode'] = True

    if multimonitorsupport:
        payload['rdpclientprofile']['multimonitorsupport'] = True

    if rdpcookievalidity:
        payload['rdpclientprofile']['rdpcookievalidity'] = True

    if addusernameinrdpfile:
        payload['rdpclientprofile']['addusernameinrdpfile'] = True

    if rdpfilename:
        payload['rdpclientprofile']['rdpfilename'] = True

    if rdphost:
        payload['rdpclientprofile']['rdphost'] = True

    if rdplistener:
        payload['rdpclientprofile']['rdplistener'] = True

    if rdpcustomparams:
        payload['rdpclientprofile']['rdpcustomparams'] = True

    if psk:
        payload['rdpclientprofile']['psk'] = True

    execution = __proxy__['citrixns.post']('config/rdpclientprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def unset_rdpserverprofile(name=None, rdpip=None, rdpport=None, psk=None, save=False):
    '''
    Unsets values from the rdpserverprofile configuration key.

    name(bool): Unsets the name value.

    rdpip(bool): Unsets the rdpip value.

    rdpport(bool): Unsets the rdpport value.

    psk(bool): Unsets the psk value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.unset_rdpserverprofile <args>

    '''

    result = {}

    payload = {'rdpserverprofile': {}}

    if name:
        payload['rdpserverprofile']['name'] = True

    if rdpip:
        payload['rdpserverprofile']['rdpip'] = True

    if rdpport:
        payload['rdpserverprofile']['rdpport'] = True

    if psk:
        payload['rdpserverprofile']['psk'] = True

    execution = __proxy__['citrixns.post']('config/rdpserverprofile?action=unset', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_rdpclientprofile(name=None, rdpurloverride=None, redirectclipboard=None, redirectdrives=None,
                            redirectprinters=None, redirectcomports=None, redirectpnpdevices=None, keyboardhook=None,
                            audiocapturemode=None, videoplaybackmode=None, multimonitorsupport=None,
                            rdpcookievalidity=None, addusernameinrdpfile=None, rdpfilename=None, rdphost=None,
                            rdplistener=None, rdpcustomparams=None, psk=None, save=False):
    '''
    Update the running configuration for the rdpclientprofile config key.

    name(str): The name of the rdp profile. Minimum length = 1

    rdpurloverride(str): This setting determines whether the RDP parameters supplied in the vpn url override those specified
        in the RDP profile. Default value: ENABLE Possible values = ENABLE, DISABLE

    redirectclipboard(str): This setting corresponds to the Clipboard check box on the Local Resources tab under Options in
        RDC. Default value: ENABLE Possible values = ENABLE, DISABLE

    redirectdrives(str): This setting corresponds to the selections for Drives under More on the Local Resources tab under
        Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    redirectprinters(str): This setting corresponds to the selection in the Printers check box on the Local Resources tab
        under Options in RDC. Default value: ENABLE Possible values = ENABLE, DISABLE

    redirectcomports(str): This setting corresponds to the selections for comports under More on the Local Resources tab
        under Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    redirectpnpdevices(str): This setting corresponds to the selections for pnpdevices under More on the Local Resources tab
        under Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    keyboardhook(str): This setting corresponds to the selection in the Keyboard drop-down list on the Local Resources tab
        under Options in RDC. Default value: InFullScreenMode Possible values = OnLocal, OnRemote, InFullScreenMode

    audiocapturemode(str): This setting corresponds to the selections in the Remote audio area on the Local Resources tab
        under Options in RDC. Default value: DISABLE Possible values = ENABLE, DISABLE

    videoplaybackmode(str): This setting determines if Remote Desktop Connection (RDC) will use RDP efficient multimedia
        streaming for video playback. Default value: ENABLE Possible values = ENABLE, DISABLE

    multimonitorsupport(str): Enable/Disable Multiple Monitor Support for Remote Desktop Connection (RDC). Default value:
        ENABLE Possible values = ENABLE, DISABLE

    rdpcookievalidity(int): RDP cookie validity period. Default value: 60 Minimum value = 60 Maximum value = 86400

    addusernameinrdpfile(str): Add username in rdp file. Default value: NO Possible values = YES, NO

    rdpfilename(str): RDP file name to be sent to End User. Minimum length = 1

    rdphost(str): Fully-qualified domain name (FQDN) of the RDP Listener. Maximum length = 252

    rdplistener(str): Fully-qualified domain name (FQDN) of the RDP Listener with the port in the format FQDN:Port. Maximum
        length = 258

    rdpcustomparams(str): Option for RDP custom parameters settings (if any). Custom params needs to be separated by ;amp;.
        Default value: 0 Minimum length = 1

    psk(str): Pre shared key value. Default value: 0

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.update_rdpclientprofile <args>

    '''

    result = {}

    payload = {'rdpclientprofile': {}}

    if name:
        payload['rdpclientprofile']['name'] = name

    if rdpurloverride:
        payload['rdpclientprofile']['rdpurloverride'] = rdpurloverride

    if redirectclipboard:
        payload['rdpclientprofile']['redirectclipboard'] = redirectclipboard

    if redirectdrives:
        payload['rdpclientprofile']['redirectdrives'] = redirectdrives

    if redirectprinters:
        payload['rdpclientprofile']['redirectprinters'] = redirectprinters

    if redirectcomports:
        payload['rdpclientprofile']['redirectcomports'] = redirectcomports

    if redirectpnpdevices:
        payload['rdpclientprofile']['redirectpnpdevices'] = redirectpnpdevices

    if keyboardhook:
        payload['rdpclientprofile']['keyboardhook'] = keyboardhook

    if audiocapturemode:
        payload['rdpclientprofile']['audiocapturemode'] = audiocapturemode

    if videoplaybackmode:
        payload['rdpclientprofile']['videoplaybackmode'] = videoplaybackmode

    if multimonitorsupport:
        payload['rdpclientprofile']['multimonitorsupport'] = multimonitorsupport

    if rdpcookievalidity:
        payload['rdpclientprofile']['rdpcookievalidity'] = rdpcookievalidity

    if addusernameinrdpfile:
        payload['rdpclientprofile']['addusernameinrdpfile'] = addusernameinrdpfile

    if rdpfilename:
        payload['rdpclientprofile']['rdpfilename'] = rdpfilename

    if rdphost:
        payload['rdpclientprofile']['rdphost'] = rdphost

    if rdplistener:
        payload['rdpclientprofile']['rdplistener'] = rdplistener

    if rdpcustomparams:
        payload['rdpclientprofile']['rdpcustomparams'] = rdpcustomparams

    if psk:
        payload['rdpclientprofile']['psk'] = psk

    execution = __proxy__['citrixns.put']('config/rdpclientprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result


def update_rdpserverprofile(name=None, rdpip=None, rdpport=None, psk=None, save=False):
    '''
    Update the running configuration for the rdpserverprofile config key.

    name(str): The name of the rdp server profile. Minimum length = 1 Maximum length = 32

    rdpip(str): IPv4 or IPv6 address of RDP listener. This terminates client RDP connections. Minimum length = 1

    rdpport(int): TCP port on which the RDP connection is established. Default value: 3389 Minimum value = 1 Maximum value =
        65535

    psk(str): Pre shared key value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' rdp.update_rdpserverprofile <args>

    '''

    result = {}

    payload = {'rdpserverprofile': {}}

    if name:
        payload['rdpserverprofile']['name'] = name

    if rdpip:
        payload['rdpserverprofile']['rdpip'] = rdpip

    if rdpport:
        payload['rdpserverprofile']['rdpport'] = rdpport

    if psk:
        payload['rdpserverprofile']['psk'] = psk

    execution = __proxy__['citrixns.put']('config/rdpserverprofile', payload)

    if execution is True:
        result['result'] = 'True'
    else:
        result['result'] = 'False'
        result['error'] = execution
        return result

    if save is True:
        result['save'] = __salt__['ns.ns.save_config']()
    else:
        result['save'] = 'False'

    return result
