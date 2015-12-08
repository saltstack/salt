# -*- coding: utf-8 -*-
'''
Support for Stormpath

.. versionadded:: 2015.8.0
'''

# Import python libs
from __future__ import absolute_import, print_function
import json
import logging

# Import salt libs
import salt.utils.http

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    if not __opts__.get('stormpath', {}).get('apiid', None):
        return False
    if not __opts__.get('stormpath', {}).get('apikey', None):
        return False
    return True


def create_account(directory_id, email, password, givenName, surname, **kwargs):
    '''
    Create an account

    CLI Examples:

        salt myminion stormpath.create_account <directory_id> shemp@example.com letmein Shemp Howard

    '''
    items = {
        'email': email,
        'password': password,
        'givenName': givenName,
        'surname': surname,
    }
    items.update(**kwargs)

    status, result = _query(
        action='directories',
        command='{0}/accounts'.format(directory_id),
        data=json.dumps(items),
        header_dict={'Content-Type': 'application/json;charset=UTF-8'},
        method='POST',
    )

    comps = result['href'].split('/')
    return show_account(comps[-1])


def list_accounts():
    '''
    Show all accounts.

    CLI Example:

        salt myminion stormpath.list_accounts

    '''
    status, result = _query(action='accounts', command='current')
    return result


def show_account(account_id=None,
                 email=None,
                 directory_id=None,
                 application_id=None,
                 group_id=None,
                 **kwargs):
    '''
    Show a specific account.

    CLI Example:

        salt myminion stormpath.show_account <account_id>

    '''
    if account_id:
        status, result = _query(
            action='accounts',
            command=account_id,
        )
        return result

    if email:
        if not directory_id and not application_id and not group_id:
            return {'Error': 'Either a directory_id, application_id, or '
                    'group_id must be specified with an email address'}
        if directory_id:
            status, result = _query(
                action='directories',
                command='{0}/accounts'.format(directory_id),
                args={'email': email}
            )
        elif application_id:
            status, result = _query(
                action='applications',
                command='{0}/accounts'.format(application_id),
                args={'email': email}
            )
        elif group_id:
            status, result = _query(
                action='groups',
                command='{0}/accounts'.format(group_id),
                args={'email': email}
            )
        return result


def update_account(account_id, key=None, value=None, items=None):
    '''
    Update one or more items for this account. Specifying an empty value will
    clear it for that account.

    CLI Examples:

        salt myminion stormpath.update_account <account_id> givenName shemp
        salt myminion stormpath.update_account <account_id> middleName ''
        salt myminion stormpath.update_account <account_id> items='{"givenName": "Shemp"}
        salt myminion stormpath.update_account <account_id> items='{"middlename": ""}

    '''
    if items is None:
        if key is None or value is None:
            return {'Error': 'At least one key/value pair is required'}
        items = {key: value}

    status, result = _query(
        action='accounts',
        command=account_id,
        data=json.dumps(items),
        header_dict={'Content-Type': 'application/json;charset=UTF-8'},
        method='POST',
    )

    return show_account(account_id)


def delete_account(account_id):
    '''
    Delete an account.

    CLI Examples:

        salt myminion stormpath.delete_account <account_id>
    '''
    _query(
        action='accounts',
        command=account_id,
        method='DELETE',
    )

    return True


def list_directories():
    '''
    Show all directories.

    CLI Example:

        salt myminion stormpath.list_directories

    '''
    tenant = show_tenant()
    tenant_id = tenant.get('href', '').split('/')[-1]
    status, result = _query(action='tenants', command='{0}/directories'.format(tenant_id))
    return result


def show_tenant():
    '''
    Get the tenant for the login being used.
    '''
    status, result = _query(action='tenants', command='current')
    return result


def _query(action=None,
           command=None,
           args=None,
           method='GET',
           header_dict=None,
           data=None):
    '''
    Make a web call to Stormpath.
    '''
    apiid = __opts__.get('stormpath', {}).get('apiid', None)
    apikey = __opts__.get('stormpath', {}).get('apikey', None)
    path = 'https://api.stormpath.com/v1/'

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('Stormpath URL: {0}'.format(path))

    if not isinstance(args, dict):
        args = {}

    if header_dict is None:
        header_dict = {}

    if method != 'POST':
        header_dict['Accept'] = 'application/json'

    decode = True
    if method == 'DELETE':
        decode = False

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        username=apiid,
        password=apikey,
        params=args,
        data=data,
        header_dict=header_dict,
        decode=decode,
        decode_type='json',
        text=True,
        status=True,
        opts=__opts__,
    )
    log.debug(
        'Stormpath Response Status Code: {0}'.format(
            result['status']
        )
    )

    return [result['status'], result.get('dict', {})]
