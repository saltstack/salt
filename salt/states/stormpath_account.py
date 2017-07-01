# -*- coding: utf-8 -*-
'''
Support for Stormpath.

.. versionadded:: 2015.8.0
'''

# Import python libs
from __future__ import absolute_import
import pprint


def __virtual__():
    '''
    Only load if the stormpath module is available in __salt__
    '''
    return 'stormpath.create_account' in __salt__


def present(name, **kwargs):
    '''
    Ensure that an account is present and properly configured

    name
        The email address associated with the Stormpath account

    directory_id
        The ID of a directory which the account belongs to. Required.

    password
        Required when creating a new account. If specified, it is advisable to
        reference the password in another database using an ``sdb://`` URL.
        Will NOT update the password if an account already exists.

    givenName
        Required when creating a new account.

    surname
        Required when creating a new account.

    username
        Optional. Must be unique across the owning directory. If not specified,
        the username will default to the email field.

    middleName
        Optional.

    status
        ``enabled`` accounts are able to login to their assigned applications,
        ``disabled`` accounts may not login to applications, ``unverified``
        accounts are disabled and have not verified their email address.

    customData.
        Optional. Must be specified as a dict.
    '''
    # Because __opts__ is not available outside of functions
    backend = __opts__.get('backend', False)
    if not backend:
        backend = 'requests'

    if backend == 'requests':
        from requests.exceptions import HTTPError
    elif backend == 'urrlib2':
        from urllib2 import HTTPError
    else:
        from tornado.httpclient import HTTPError

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    info = {}
    try:
        result = __salt__['stormpath.show_account'](email=name, **kwargs)
        if len(result['items']) > 0:
            info = result['items'][0]
    except HTTPError:
        pass
    needs_update = {}
    if info.get('email', False):
        for field in kwargs:
            if info.get(field, None) != kwargs[field]:
                needs_update[field] = kwargs[field]
        del needs_update['directory_id']
        if 'password' in needs_update:
            del needs_update['password']
        if len(needs_update.keys()) < 1:
            ret['result'] = True
            ret['comment'] = 'Stormpath account {0} already exists and is correct'.format(name)
            return ret
    if __opts__['test']:
        if len(needs_update.keys()) < 1:
            ret['comment'] = 'Stormpath account {0} needs to be created'.format(name)
        else:
            if 'password' in needs_update:
                needs_update['password'] = '**HIDDEN**'
            ret['comment'] = ('Stormpath account {0} needs the following '
                'fields to be updated: '.format(', '.join(needs_update)))
        return ret
    if len(needs_update.keys()) < 1:
        info = __salt__['stormpath.create_account'](email=name, **kwargs)
        comps = info['href'].split('/')
        account_id = comps[-1]
        ret['changes'] = info
        ret['result'] = True
        kwargs['password'] = '**HIDDEN**'
        ret['comment'] = 'Created account ID {0} ({1}): {2}'.format(
            account_id, name, pprint.pformat(kwargs))
        return ret
    comps = info['href'].split('/')
    account_id = comps[-1]
    result = __salt__['stormpath.update_account'](account_id, items=needs_update)
    if result.get('href', None):
        ret['changes'] = needs_update
        ret['result'] = True
        if 'password' in needs_update:
            needs_update['password'] = '**HIDDEN**'
        ret['comment'] = 'Set the following fields for account ID {0} ({1}): {2}'.format(
            account_id, name, pprint.pformat(needs_update))
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to set the following fields for account ID {0} ({1}): {2}'.format(
            account_id, name, pprint.pformat(needs_update))
        return ret


def absent(name, directory_id=None):
    '''
    Ensure that an account associated with the given email address is absent.
    Will search all directories for the account, unless a directory_id is
    specified.

    name
        The email address of the account to delete.

    directory_id
        Optional. The ID of the directory that the account is expected to belong
        to. If not specified, then a list of directories will be retrieved, and
        each will be scanned for the account. Specifying a directory_id will
        therefore cut down on the number of requests to Stormpath, and increase
        performance of this state.
    '''
    # Because __opts__ is not available outside of functions
    backend = __opts__.get('backend', False)
    if not backend:
        backend = 'requests'

    if backend == 'requests':
        from requests.exceptions import HTTPError
    elif backend == 'urrlib2':
        from urllib2 import HTTPError
    else:
        from tornado.httpclient import HTTPError

    ret = {'name': name,
           'changes': {},
           'result': None,
           'comment': ''}
    info = {}
    if directory_id is None:
        dirs = __salt__['stormpath.list_directories']()
        for dir_ in dirs.get('items', []):
            try:
                comps = dir_.get('href', '').split('/')
                directory_id = comps[-1]
                info = __salt__['stormpath.show_account'](email=name, directory_id=directory_id)
                if len(info.get('items', [])) > 0:
                    info = info['items'][0]
                    break
            except HTTPError:
                pass
    else:
        info = __salt__['stormpath.show_account'](email=name, directory_id=directory_id)
        info = info['items'][0]
    if 'items' in info:
        ret['result'] = True
        ret['comment'] = 'Stormpath account {0} already absent'.format(name)
        return ret
    if __opts__['test']:
        ret['comment'] = 'Stormpath account {0} needs to be deleted'.format(name)
        return ret
    comps = info['href'].split('/')
    account_id = comps[-1]
    if __salt__['stormpath.delete_account'](account_id):
        ret['changes'] = {'deleted': account_id}
        ret['result'] = True
        ret['comment'] = 'Stormpath account {0} was deleted'.format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = 'Failed to delete Stormpath account {0}'.format(name)
        return ret
