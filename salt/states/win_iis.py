# -*- coding: utf-8 -*-
'''
Microsoft IIS site management

This module provides the ability to add/remove websites and application pools
from Microsoft IIS.

.. versionadded:: 2016.3.0

'''


from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)


# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False


def deployed(
        name,
        protocol,
        sourcepath,
        port,
        apppool='',
        hostheader='',
        ipaddress=''):
    '''
    Ensure the website has been deployed. This only validates against the
    website name and will not update information on existing websites with the
    same name. If the website name doesn't exist it will create with the
    provided parameters.

    name
        Name of the website in IIS.

    protocol
        http or https

    sourcepath
        The directory path on the IIS server to use as a root file store.
        example: c:\\websites\\website1

    port
        The network port to listen for traffic.
        example: 80

    apppool
        The application pool to configure for the website. Must already exist.

    hostheader
        The hostheader to route to this website.

    ipaddress
        The website ipaddress

    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    sitelist = __salt__['win_iis.list_sites']()

    if 'was not loaded' in sitelist:
        ret['result'] = False
        ret['comment'] = 'IIS is not installed. Please verify your installation of IIS.'
        return ret
    else:
        if name in sitelist:
            # Site already exist
            # ret['changes'] = {'results': '{0} already exist'.format(name)}
            ret['result'] = True
            ret['comment'] = 'The website you are trying to create already exists.'
        else:
            # Site doesn exist create site

            sitecreated = __salt__['win_iis.create_site'](
                    name,
                    protocol,
                    sourcepath,
                    port,
                    apppool,
                    hostheader,
                    ipaddress)
            ret['changes'] = {'results': '{0} site created'.format(name)}
            ret['result'] = True
            ret['comment'] = 'The website has been created.'

    return ret


def remove_site(name):
    # Remove IIS website
    '''
    Remove an existing website from the webserver.

    name
        The website name as shown in IIS.


    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    siteremove = __salt__['win_iis.remove_site'](name)

    if 'was not loaded' in siteremove:
        ret['result'] = False
        ret['comment'] = 'IIS is not installed. Please verify your installation of IIS.'
        return ret
    elif 'Cannot find path' in siteremove:
        ret['result'] = True
        ret['comment'] = 'The website was not found.'
        return ret
    elif len(siteremove) == 0:
        ret['result'] = True
        ret['comment'] = 'The website {0} has been removed'.format(name)
        return ret
    else:
        ret['result'] = 'Error'
        ret['comment'] = siteremove

    return ret


def create_apppool(name):
    # Confirm IIS Application is deployed

    '''
    Creates an IIS application pool.

    name
        The name of the application pool to use

    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    apppoollist = __salt__['win_iis.list_apppools']()

    if 'was not loaded' in apppoollist:
        ret['result'] = False
        ret['comment'] = 'IIS is not installed. Please verify your installation of IIS'
        return ret
    else:
        if name in apppoollist:
            # AppPool already exist
            # ret['changes'] = {'results': '{0} already exist'.format(name)}
            ret['result'] = True
            ret['comment'] = 'The application pool already exists.'
        else:
            # AppPool doesn't exist create pool

            poolcreated = __salt__['win_iis.create_apppool'](
                    name)
            ret['changes'] = {'results': '{0} Application Pool created'.format(name)}
            ret['result'] = True
            ret['comment'] = 'Application Pool created'

    return ret


def remove_apppool(name):
    # Remove IIS AppPool
    '''
    Removes an existing Application Pool from the server

    name
        The name of the application pool to remove

    '''

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    apppool = __salt__['win_iis.remove_apppool'](name)

    if 'was not loaded' in apppool:
        ret['result'] = False
        ret['comment'] = 'IIS is not installed. Please verify your installation of IIS.'
        return ret
    elif 'Cannot find path' in apppool:
        ret['result'] = True
        ret['comment'] = 'The application pool has already been removed.'
        return ret
    elif len(apppool) == 0:
        ret['result'] = True
        ret['comment'] = 'Application Pool {0} has been removed'.format(name)
        return ret
    else:
        ret['result'] = 'Error'
        ret['comment'] = apppool

    return ret
