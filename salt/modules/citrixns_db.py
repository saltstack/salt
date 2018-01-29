# -*- coding: utf-8 -*-
'''
A module to manage contents on a Citrix Netscaler under the db key.

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

__virtualname__ = 'db'


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

    return False, 'The db execution module can only be loaded for citrixns proxy minions.'


def add_dbdbprofile(name=None, interpretquery=None, stickiness=None, kcdaccount=None, conmultiplex=None,
                    enablecachingconmuxoff=None, save=False):
    '''
    Add a new dbdbprofile to the running configuration.

    name(str): Name for the database profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters. Cannot be changed after the profile is created.  CLI Users: If the name includes one
        or more spaces, enclose the name in double or single quotation marks (for example, "my profile" or my profile). .
        Minimum length = 1 Maximum length = 127

    interpretquery(str): If ENABLED, inspect the query and update the connection information, if required. If DISABLED,
        forward the query to the server. Default value: YES Possible values = YES, NO

    stickiness(str): If the queries are related to each other, forward to the same backend server. Default value: NO Possible
        values = YES, NO

    kcdaccount(str): Name of the KCD account that is used for Windows authentication. Minimum length = 1 Maximum length =
        127

    conmultiplex(str): Use the same server-side connection for multiple client-side requests. Default is enabled. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    enablecachingconmuxoff(str): Enable caching when connection multiplexing is OFF. Default value: DISABLED Possible values
        = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' db.add_dbdbprofile <args>

    '''

    result = {}

    payload = {'dbdbprofile': {}}

    if name:
        payload['dbdbprofile']['name'] = name

    if interpretquery:
        payload['dbdbprofile']['interpretquery'] = interpretquery

    if stickiness:
        payload['dbdbprofile']['stickiness'] = stickiness

    if kcdaccount:
        payload['dbdbprofile']['kcdaccount'] = kcdaccount

    if conmultiplex:
        payload['dbdbprofile']['conmultiplex'] = conmultiplex

    if enablecachingconmuxoff:
        payload['dbdbprofile']['enablecachingconmuxoff'] = enablecachingconmuxoff

    execution = __proxy__['citrixns.post']('config/dbdbprofile', payload)

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


def add_dbuser(username=None, password=None, loggedin=None, save=False):
    '''
    Add a new dbuser to the running configuration.

    username(str): Name of the database user. Must be the same as the user name specified in the database. Minimum length =
        1

    password(str): Password for logging on to the database. Must be the same as the password specified in the database.
        Minimum length = 1

    loggedin(bool): Display the names of all database users currently logged on to the NetScaler appliance.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' db.add_dbuser <args>

    '''

    result = {}

    payload = {'dbuser': {}}

    if username:
        payload['dbuser']['username'] = username

    if password:
        payload['dbuser']['password'] = password

    if loggedin:
        payload['dbuser']['loggedin'] = loggedin

    execution = __proxy__['citrixns.post']('config/dbuser', payload)

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


def get_dbdbprofile(name=None, interpretquery=None, stickiness=None, kcdaccount=None, conmultiplex=None,
                    enablecachingconmuxoff=None):
    '''
    Show the running configuration for the dbdbprofile config key.

    name(str): Filters results that only match the name field.

    interpretquery(str): Filters results that only match the interpretquery field.

    stickiness(str): Filters results that only match the stickiness field.

    kcdaccount(str): Filters results that only match the kcdaccount field.

    conmultiplex(str): Filters results that only match the conmultiplex field.

    enablecachingconmuxoff(str): Filters results that only match the enablecachingconmuxoff field.

    CLI Example:

    .. code-block:: bash

    salt '*' db.get_dbdbprofile

    '''

    search_filter = []

    if name:
        search_filter.append(['name', name])

    if interpretquery:
        search_filter.append(['interpretquery', interpretquery])

    if stickiness:
        search_filter.append(['stickiness', stickiness])

    if kcdaccount:
        search_filter.append(['kcdaccount', kcdaccount])

    if conmultiplex:
        search_filter.append(['conmultiplex', conmultiplex])

    if enablecachingconmuxoff:
        search_filter.append(['enablecachingconmuxoff', enablecachingconmuxoff])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dbdbprofile{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dbdbprofile')

    return response


def get_dbuser(username=None, password=None, loggedin=None):
    '''
    Show the running configuration for the dbuser config key.

    username(str): Filters results that only match the username field.

    password(str): Filters results that only match the password field.

    loggedin(bool): Filters results that only match the loggedin field.

    CLI Example:

    .. code-block:: bash

    salt '*' db.get_dbuser

    '''

    search_filter = []

    if username:
        search_filter.append(['username', username])

    if password:
        search_filter.append(['password', password])

    if loggedin:
        search_filter.append(['loggedin', loggedin])

    response = salt.proxy.citrixns.parse_return(
            __proxy__['citrixns.get']('config/dbuser{0}'.format(
                    salt.proxy.citrixns.build_filter(search_filter))), 'dbuser')

    return response


def unset_dbdbprofile(name=None, interpretquery=None, stickiness=None, kcdaccount=None, conmultiplex=None,
                      enablecachingconmuxoff=None, save=False):
    '''
    Unsets values from the dbdbprofile configuration key.

    name(bool): Unsets the name value.

    interpretquery(bool): Unsets the interpretquery value.

    stickiness(bool): Unsets the stickiness value.

    kcdaccount(bool): Unsets the kcdaccount value.

    conmultiplex(bool): Unsets the conmultiplex value.

    enablecachingconmuxoff(bool): Unsets the enablecachingconmuxoff value.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' db.unset_dbdbprofile <args>

    '''

    result = {}

    payload = {'dbdbprofile': {}}

    if name:
        payload['dbdbprofile']['name'] = True

    if interpretquery:
        payload['dbdbprofile']['interpretquery'] = True

    if stickiness:
        payload['dbdbprofile']['stickiness'] = True

    if kcdaccount:
        payload['dbdbprofile']['kcdaccount'] = True

    if conmultiplex:
        payload['dbdbprofile']['conmultiplex'] = True

    if enablecachingconmuxoff:
        payload['dbdbprofile']['enablecachingconmuxoff'] = True

    execution = __proxy__['citrixns.post']('config/dbdbprofile?action=unset', payload)

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


def update_dbdbprofile(name=None, interpretquery=None, stickiness=None, kcdaccount=None, conmultiplex=None,
                       enablecachingconmuxoff=None, save=False):
    '''
    Update the running configuration for the dbdbprofile config key.

    name(str): Name for the database profile. Must begin with an ASCII alphanumeric or underscore (_) character, and must
        contain only ASCII alphanumeric, underscore, hash (#), period (.), space, colon (:), at sign (@), equal sign (=),
        and hyphen (-) characters. Cannot be changed after the profile is created.  CLI Users: If the name includes one
        or more spaces, enclose the name in double or single quotation marks (for example, "my profile" or my profile). .
        Minimum length = 1 Maximum length = 127

    interpretquery(str): If ENABLED, inspect the query and update the connection information, if required. If DISABLED,
        forward the query to the server. Default value: YES Possible values = YES, NO

    stickiness(str): If the queries are related to each other, forward to the same backend server. Default value: NO Possible
        values = YES, NO

    kcdaccount(str): Name of the KCD account that is used for Windows authentication. Minimum length = 1 Maximum length =
        127

    conmultiplex(str): Use the same server-side connection for multiple client-side requests. Default is enabled. Default
        value: ENABLED Possible values = ENABLED, DISABLED

    enablecachingconmuxoff(str): Enable caching when connection multiplexing is OFF. Default value: DISABLED Possible values
        = ENABLED, DISABLED

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' db.update_dbdbprofile <args>

    '''

    result = {}

    payload = {'dbdbprofile': {}}

    if name:
        payload['dbdbprofile']['name'] = name

    if interpretquery:
        payload['dbdbprofile']['interpretquery'] = interpretquery

    if stickiness:
        payload['dbdbprofile']['stickiness'] = stickiness

    if kcdaccount:
        payload['dbdbprofile']['kcdaccount'] = kcdaccount

    if conmultiplex:
        payload['dbdbprofile']['conmultiplex'] = conmultiplex

    if enablecachingconmuxoff:
        payload['dbdbprofile']['enablecachingconmuxoff'] = enablecachingconmuxoff

    execution = __proxy__['citrixns.put']('config/dbdbprofile', payload)

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


def update_dbuser(username=None, password=None, loggedin=None, save=False):
    '''
    Update the running configuration for the dbuser config key.

    username(str): Name of the database user. Must be the same as the user name specified in the database. Minimum length =
        1

    password(str): Password for logging on to the database. Must be the same as the password specified in the database.
        Minimum length = 1

    loggedin(bool): Display the names of all database users currently logged on to the NetScaler appliance.

    save(bool): Instructs the Netscaler to save the running configuration after execution.

    CLI Example:

    .. code-block:: bash

    salt '*' db.update_dbuser <args>

    '''

    result = {}

    payload = {'dbuser': {}}

    if username:
        payload['dbuser']['username'] = username

    if password:
        payload['dbuser']['password'] = password

    if loggedin:
        payload['dbuser']['loggedin'] = loggedin

    execution = __proxy__['citrixns.put']('config/dbuser', payload)

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
