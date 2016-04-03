# -*- coding: utf-8 -*-
'''
Microsoft IIS site management

This module provides the ability to add/remove websites and application pools
from Microsoft IIS.

.. versionadded:: 2016.3.0

'''

# Import python libs
from __future__ import absolute_import


# Define the module's virtual name
__virtualname__ = 'win_iis'


def __virtual__():
    '''
    Load only on minions that have the win_iis module.
    '''
    if 'win_iis.create_site' in __salt__:
        return __virtualname__
    return False


def deployed(name, sourcepath, apppool='', hostheader='', ipaddress='*', port=80, protocol='http'):
    '''
    Ensure the website has been deployed. This only validates against the
    website name and will not update information on existing websites with the
    same name. If the website name doesn't exist it will create with the
    provided parameters.

    name
        Name of the website in IIS.

    sourcepath
        The directory path on the IIS server to use as a root file store.
        example: c:\\websites\\website1

    apppool
        The application pool to configure for the website. Must already exist.

    hostheader
        The hostheader to route to this website.

    ipaddress
        The website ipaddress

    port
        The network port to listen for traffic.
        example: 80

    protocol
        http or https
    '''
    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}

    current_sites = __salt__['win_iis.list_sites']()

    if name in current_sites:
        ret['comment'] = 'Site already present: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Site will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created site: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_site'](name, sourcepath, apppool,
                                                        hostheader, ipaddress, port,
                                                        protocol)
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

    current_sites = __salt__['win_iis.list_sites']()

    if name not in current_sites:
        ret['comment'] = 'Site has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Site will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        ret['comment'] = 'Removed site: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_site'](name)
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

    current_apppools = __salt__['win_iis.list_apppools']()

    if name in current_apppools:
        ret['comment'] = 'Application pool already present: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Application pool will be created: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
    else:
        ret['comment'] = 'Created application pool: {0}'.format(name)
        ret['changes'] = {'old': None,
                          'new': name}
        ret['result'] = __salt__['win_iis.create_apppool'](name)
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

    current_apppools = __salt__['win_iis.list_apppools']()

    if name not in current_apppools:
        ret['comment'] = 'Application pool has already been removed: {0}'.format(name)
        ret['result'] = True
    elif __opts__['test']:
        ret['comment'] = 'Application pool will be removed: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
    else:
        ret['comment'] = 'Removed application pool: {0}'.format(name)
        ret['changes'] = {'old': name,
                          'new': None}
        ret['result'] = __salt__['win_iis.remove_apppool'](name)
    return ret
