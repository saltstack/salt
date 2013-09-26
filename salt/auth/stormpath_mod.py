# -*- coding: utf-8 -*-
'''
Salt Stormpath Authentication

Module to provide authentication using Stormpath as the backend.

:depends:   - stormpath-sdk Python module
:configuration: This module requires the development branch of the
    stormpath-sdk which can be found here:
    https://github.com/stormpath/stormpath-sdk-python

    The following config items are required in the master config::

        stormpath.api_key_file: <path/to/apiKey.properties>
        stormpath.app_url: <Rest url of your Stormpath application>

    Ensure that your apiKey.properties is readable by the user the Salt Master
    is running as, but not readable by other system users.
'''
try:
    from stormpath import Client
    HAS_STORMPATH = True
except ImportError:
    HAS_STORMPATH = False


def __virtual__():
    '''
    Only load if stormpath is installed
    '''
    if HAS_STORMPATH:
        return 'stormpath'
    else:
        return False


def auth(username, password):
    '''
    Try and authenticate
    '''
    api_key_file = __opts__['stormpath.api_key_file']
    app_url = __opts__['stormpath.app_url']
    client = Client(api_key_file_location=api_key_file)
    app = client.applications.get(app_url)
    try:
        account = app.authenticate_account(username, password)
        return True
    except Exception:
        return False
