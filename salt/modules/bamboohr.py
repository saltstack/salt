# -*- coding: utf-8 -*-
'''
Support for BambooHR

.. versionadded:: 2015.8.0

Requires a ``subdomain`` and an ``apikey`` in ``/etc/salt/minion``:

.. code-block: yaml

    bamboohr:
      apikey: 012345678901234567890
      subdomain: mycompany
'''

# Import python libs
from __future__ import absolute_import, print_function
import yaml
import logging

# Import salt libs
import salt.utils.http
import salt.ext.six as six
from salt._compat import ElementTree as ET

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load the module if apache is installed
    '''
    if _apikey():
        return True
    return False


def _apikey():
    '''
    Get the API key
    '''
    return __opts__.get('bamboohr', {}).get('apikey', None)


def list_employees(order_by='id'):
    '''
    Show all employees for this company.

    CLI Example:

        salt myminion bamboohr.list_employees

    By default, the return data will be keyed by ID. However, it can be ordered
    by any other field. Keep in mind that if the field that is chosen contains
    duplicate values (i.e., location is used, for a company which only has one
    location), then each duplicate value will be overwritten by the previous.
    Therefore, it is advisable to only sort by fields that are guaranteed to be
    unique.

    CLI Examples:

        salt myminion bamboohr.list_employees order_by=id
        salt myminion bamboohr.list_employees order_by=displayName
        salt myminion bamboohr.list_employees order_by=workEmail
    '''
    ret = {}
    status, result = _query(action='employees', command='directory')
    root = ET.fromstring(result)
    directory = root.getchildren()
    for cat in directory:
        if cat.tag != 'employees':
            continue
        for item in cat:
            emp_id = item.items()[0][1]
            emp_ret = {'id': emp_id}
            for details in item.getchildren():
                emp_ret[details.items()[0][1]] = details.text
            ret[emp_ret[order_by]] = emp_ret
    return ret


def show_employee(emp_id, fields=None):
    '''
    Show all employees for this company.

    CLI Example:

        salt myminion bamboohr.show_employee 1138

    By default, the fields normally returned from bamboohr.list_employees are
    returned. These fields are:

        - canUploadPhoto
        - department
        - displayName
        - firstName
        - id
        - jobTitle
        - lastName
        - location
        - mobilePhone
        - nickname
        - photoUploaded
        - photoUrl
        - workEmail
        - workPhone
        - workPhoneExtension

    If needed, a different set of fields may be specified, separated by commas:

    CLI Example:

        salt myminion bamboohr.show_employee 1138 displayName,dateOfBirth

    A list of available fields can be found at
    http://www.bamboohr.com/api/documentation/employees.php
    '''
    ret = {}
    if fields is None:
        fields = ','.join((
            'canUploadPhoto',
            'department',
            'displayName',
            'firstName',
            'id',
            'jobTitle',
            'lastName',
            'location',
            'mobilePhone',
            'nickname',
            'photoUploaded',
            'photoUrl',
            'workEmail',
            'workPhone',
            'workPhoneExtension',
        ))

    status, result = _query(
        action='employees',
        command=emp_id,
        args={'fields': fields}
    )

    root = ET.fromstring(result)
    items = root.getchildren()

    ret = {'id': emp_id}
    for item in items:
        ret[item.items()[0][1]] = item.text
    return ret


def update_employee(emp_id, key=None, value=None, items=None):
    '''
    Update one or more items for this employee. Specifying an empty value will
    clear it for that employee.

    CLI Examples:

        salt myminion bamboohr.update_employee 1138 nickname Curly
        salt myminion bamboohr.update_employee 1138 nickname ''
        salt myminion bamboohr.update_employee 1138 items='{"nickname": "Curly"}
        salt myminion bamboohr.update_employee 1138 items='{"nickname": ""}
    '''
    if items is None:
        if key is None or value is None:
            return {'Error': 'At least one key/value pair is required'}
        items = {key: value}
    elif isinstance(items, six.string_types):
        items = yaml.safe_load(items)

    xml_items = ''
    for pair in items.keys():
        xml_items += '<field id="{0}">{1}</field>'.format(pair, items[pair])
    xml_items = '<employee>{0}</employee>'.format(xml_items)

    status, result = _query(
        action='employees',
        command=emp_id,
        data=xml_items,
        method='POST',
    )

    return show_employee(emp_id, ','.join(items.keys()))


def list_users(order_by='id'):
    '''
    Show all users for this company.

    CLI Example:

        salt myminion bamboohr.list_users

    By default, the return data will be keyed by ID. However, it can be ordered
    by any other field. Keep in mind that if the field that is chosen contains
    duplicate values (i.e., location is used, for a company which only has one
    location), then each duplicate value will be overwritten by the previous.
    Therefore, it is advisable to only sort by fields that are guaranteed to be
    unique.

    CLI Examples:

        salt myminion bamboohr.list_users order_by=id
        salt myminion bamboohr.list_users order_by=email
    '''
    ret = {}
    status, result = _query(action='meta', command='users')
    root = ET.fromstring(result)
    users = root.getchildren()
    for user in users:
        user_id = None
        user_ret = {}
        for item in user.items():
            user_ret[item[0]] = item[1]
            if item[0] == 'id':
                user_id = item[1]
        for item in user.getchildren():
            user_ret[item.tag] = item.text
        ret[user_ret[order_by]] = user_ret
    return ret


def list_meta_fields():
    '''
    Show all meta data fields for this company.

    CLI Example:

        salt myminion bamboohr.list_meta_fields
    '''
    ret = {}
    status, result = _query(action='meta', command='fields')
    root = ET.fromstring(result)
    fields = root.getchildren()
    for field in fields:
        field_id = None
        field_ret = {'name': field.text}
        for item in field.items():
            field_ret[item[0]] = item[1]
            if item[0] == 'id':
                field_id = item[1]
        ret[field_id] = field_ret
    return ret


def _query(action=None,
           command=None,
           args=None,
           method='GET',
           data=None):
    '''
    Make a web call to BambooHR

    The password can be any random text, so we chose Salty text.
    '''
    subdomain = __opts__.get('bamboohr', {}).get('subdomain', None)
    path = 'https://api.bamboohr.com/api/gateway.php/{0}/v1/'.format(
        subdomain
    )

    if action:
        path += action

    if command:
        path += '/{0}'.format(command)

    log.debug('BambooHR URL: {0}'.format(path))

    if not isinstance(args, dict):
        args = {}

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        username=_apikey(),
        password='saltypork',
        params=args,
        data=data,
        decode=False,
        text=True,
        status=True,
        opts=__opts__,
    )
    log.debug(
        'BambooHR Response Status Code: {0}'.format(
            result['status']
        )
    )

    return [result['status'], result['text']]
