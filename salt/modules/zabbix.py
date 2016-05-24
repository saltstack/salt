# -*- coding: utf-8 -*-
'''
Support for Zabbix

:optdepends:    - zabbix server

:configuration: This module is not usable until the zabbix user and zabbix password are specified either in a pillar
    or in the minion's config file. Zabbix url should be also specified.

    .. code-block:: yaml

        zabbix.user: Admin
        zabbix.password: mypassword
        zabbix.url: http://127.0.0.1/zabbix/api_jsonrpc.php


    Connection arguments from the minion config file can be overridden on the CLI by using arguments with
    _connection_ prefix.

    .. code-block:: bash

        zabbix.apiinfo_version _connection_user=Admin _connection_password=zabbix _connection_url=http://host/zabbix/

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>
'''
from __future__ import absolute_import
# Import python libs
import logging
import socket
import json
from distutils.version import LooseVersion

# Import salt libs
import salt.utils
from salt.ext.six.moves.urllib.error import HTTPError, URLError  # pylint: disable=import-error,no-name-in-module

log = logging.getLogger(__name__)

INTERFACE_DEFAULT_PORTS = [10050, 161, 623, 12345]

# Define the module's virtual name
__virtualname__ = 'zabbix'


def __virtual__():
    '''
    Only load the module if Zabbix server is installed
    '''
    if salt.utils.which('zabbix_server'):
        return __virtualname__
    return (False, 'The zabbix execution module cannot be loaded: zabbix not installed.')


def _frontend_url():
    '''
    Tries to guess the url of zabbix frontend.

    .. versionadded:: 2016.3.0
    '''
    hostname = socket.gethostname()
    frontend_url = 'http://' + hostname + '/zabbix/api_jsonrpc.php'
    try:
        try:
            response = salt.utils.http.query(frontend_url)
            error = response['error']
        except HTTPError as http_e:
            error = str(http_e)
        if error.find('412: Precondition Failed'):
            return frontend_url
        else:
            raise KeyError
    except (ValueError, KeyError):
        return False


def _query(method, params, url, auth=None):
    '''
    JSON request to Zabbix API.

    .. versionadded:: 2016.3.0

    :param method: actual operation to perform via the API
    :param params: parameters required for specific method
    :param url: url of zabbix api
    :param auth: auth token for zabbix api (only for methods with required authentication)

    :return: Response from API with desired data in JSON format.
    '''

    unauthenticated_methods = ['user.login', 'apiinfo.version', ]

    header_dict = {'Content-type': 'application/json'}
    data = {'jsonrpc': '2.0', 'id': 0, 'method': method, 'params': params}

    if method not in unauthenticated_methods:
        data['auth'] = auth

    data = json.dumps(data)

    try:
        result = salt.utils.http.query(url,
                                       method='POST',
                                       data=data,
                                       header_dict=header_dict,
                                       decode_type='json',
                                       decode=True,)
        ret = result.get('dict', {})
        return ret
    except (URLError, socket.gaierror):
        return {}


def _login(**kwargs):
    '''
    Log in to the API and generate the authentication token.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: On success connargs dictionary with auth token and frontend url, False on failure.

    '''
    connargs = dict()

    def _connarg(name, key=None):
        '''
        Add key to connargs, only if name exists in our kwargs or, as zabbix.<name> in __opts__ or __pillar__

        Evaluate in said order - kwargs, opts, then pillar. To avoid collision with other functions,
        kwargs-based connection arguments are prefixed with 'connection_' (i.e. '_connection_user', etc.).

        Inspired by mysql salt module.
        '''
        if key is None:
            key = name

        if name in kwargs:
            connargs[key] = kwargs[name]
        else:
            prefix = '_connection_'
            if name.startswith(prefix):
                try:
                    name = name[len(prefix):]
                except IndexError:
                    return
            val = __salt__['config.option']('zabbix.{0}'.format(name), None)
            if val is not None:
                connargs[key] = val

    _connarg('_connection_user', 'user')
    _connarg('_connection_password', 'password')
    _connarg('_connection_url', 'url')

    if 'url' not in connargs:
        connargs['url'] = _frontend_url()

    try:
        if connargs['user'] and connargs['password'] and connargs['url']:
            params = {'user': connargs['user'], 'password': connargs['password']}
            method = 'user.login'
            ret = _query(method, params, connargs['url'])
            auth = ret['result']
            connargs['auth'] = auth
            connargs.pop('user', None)
            connargs.pop('password', None)
            return connargs
        else:
            raise KeyError
    except KeyError:
        return False


def _params_extend(params, _ignore_name=False, **kwargs):
    '''
    Extends the params dictionary by values from keyword arguments.

    .. versionadded:: 2016.3.0

    :param params: Dictionary with parameters for zabbix API.
    :param _ignore_name: Salt State module is passing first line as 'name' parameter. If API uses optional parameter
    'name' (for ex. host_create, user_create method), please use 'visible_name' or 'firstname' instead of 'name' to
    not mess these values.
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Extended params dictionary with parameters.

    '''
    # extend params value by optional zabbix API parameters
    for key in kwargs.keys():
        if not key.startswith('_'):
            params.setdefault(key, kwargs[key])

    # ignore name parameter passed from Salt state module, use firstname or visible_name instead
    if _ignore_name:
        params.pop('name', None)
        if 'firstname' in params:
            params['name'] = params.pop('firstname')
        elif 'visible_name' in params:
            params['name'] = params.pop('visible_name')

    return params


def apiinfo_version(**connection_args):
    '''
    Retrieve the version of the Zabbix API.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: On success string with Zabbix API version, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.apiinfo_version
    '''
    conn_args = _login(**connection_args)

    try:
        if conn_args:
            method = 'apiinfo.version'
            params = {}
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def user_create(alias, passwd, usrgrps, **connection_args):
    '''
    Create new zabbix user.
    NOTE: This function accepts all standard user properties: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.0/manual/appendix/api/user/definitions#user

    .. versionadded:: 2016.3.0

    :param alias: user alias
    :param passwd: user's password
    :param usrgrps: user groups to add the user to

    :param _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    :param firstname: string with firstname of the user, use 'firstname' instead of 'name' parameter to not mess
                      with value supplied from Salt sls file.

    :return: On success string with id of the created user.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_create james password007 '[7, 12]' firstname='James Bond'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.create'
            params = {"alias": alias, "passwd": passwd, "usrgrps": []}
            # User groups
            if not isinstance(usrgrps, list):
                usrgrps = [usrgrps]
            for usrgrp in usrgrps:
                params['usrgrps'].append({"usrgrpid": usrgrp})

            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['userids']
        else:
            raise KeyError
    except KeyError:
        return ret


def user_delete(users, **connection_args):
    '''
    Delete zabbix users.

    .. versionadded:: 2016.3.0

    :param users: array of users (userids) to delete
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: On success array with userids of deleted users.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_delete 15
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.delete'
            if not isinstance(users, list):
                params = [users]
            else:
                params = users

            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['userids']
        else:
            raise KeyError
    except KeyError:
        return ret


def user_exists(alias, **connection_args):
    '''
    Checks if user with given alias exists.

    .. versionadded:: 2016.3.0

    :param alias: user alias
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: True if user exists, else False.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_exists james
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.get'
            params = {"output": "extend", "filter": {"alias": alias}}
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return True if len(ret['result']) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return False


def user_get(alias=None, userids=None, **connection_args):
    '''
    Retrieve users according to the given parameters.

    .. versionadded:: 2016.3.0

    :param alias: user alias
    :param userids: return only users with the given IDs
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with details of convenient users, False on failure of if no user found.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_get james
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.get'
            params = {"output": "extend", "filter": {}}
            if not userids and not alias:
                return {'result': False, 'comment': 'Please submit alias or userids parameter to retrieve users.'}
            if alias:
                params['filter'].setdefault('alias', alias)
            if userids:
                params.setdefault('userids', userids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result'] if len(ret['result']) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return False


def user_update(userid, **connection_args):
    '''
    Update existing users. NOTE: This function accepts all standard user properties: keyword argument names differ
    depending on your zabbix version, see:
    https://www.zabbix.com/documentation/2.0/manual/appendix/api/user/definitions#user

    .. versionadded:: 2016.3.0

    :param userid: id of the user to update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Id of the updated user on success.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_update 16 visible_name='James Brown'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.update'
            params = {"userid": userid, }
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['userids']
        else:
            raise KeyError
    except KeyError:
        return ret


def user_getmedia(userids=None, **connection_args):
    '''
    Retrieve media according to the given parameters NOTE: This function accepts all standard usermedia.get properties:
    keyword argument names differ depending on your zabbix version, see:
    https://www.zabbix.com/documentation/3.2/manual/api/reference/usermedia/get

    .. versionadded:: 2016.3.0

    :param userids: return only media that are used by the given users

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: List of retreived media, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_getmedia
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usermedia.get'
            if userids:
                params = {"userids": userids}
            else:
                params = {}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def user_addmedia(userids, active, mediatypeid, period, sendto, severity, **connection_args):
    '''
    Add new media to multiple users.

    .. versionadded:: 2016.3.0

    :param userids: ID of the user that uses the media
    :param active: Whether the media is enabled (0 enabled, 1 disabled)
    :param mediatypeid: ID of the media type used by the media
    :param period: Time when the notifications can be sent as a time period
    :param sendto: Address, user name or other identifier of the recipient
    :param severity: Trigger severities to send notifications about
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the created media.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_addmedia 4 active=0 mediatypeid=1 period='1-7,00:00-24:00' sendto='support2@example.com'
        severity=63

    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.addmedia'
            params = {"users": []}
            # Users
            if not isinstance(userids, list):
                userids = [userids]
            for user in userids:
                params['users'].append({"userid": user})
            # Medias
            params['medias'] = [{"active": active, "mediatypeid": mediatypeid, "period": period,
                                 "sendto": sendto, "severity": severity}, ]

            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['mediaids']
        else:
            raise KeyError
    except KeyError:
        return ret


def user_deletemedia(mediaids, **connection_args):
    '''
    Delete media by id.

    .. versionadded:: 2016.3.0

    :param mediaids: IDs of the media to delete
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the deleted media, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_deletemedia 27
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.deletemedia'

            if not isinstance(mediaids, list):
                mediaids = [mediaids]
            params = mediaids
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['mediaids']
        else:
            raise KeyError
    except KeyError:
        return ret


def user_list(**connection_args):
    '''
    Retrieve all of the configured users.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with user details.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_list
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.get'
            params = {"output": "extend"}
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_create(name, **connection_args):
    '''
    Create new user group.
    NOTE: This function accepts all standard user group properties: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.0/manual/appendix/api/usergroup/definitions#user_group

    .. versionadded:: 2016.3.0

    :param name: name of the user group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return:  IDs of the created user groups.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_create GroupName
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usergroup.create'
            params = {"name": name}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['usrgrpids']
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_delete(usergroupids, **connection_args):
    '''
    .. versionadded:: 2016.3.0

    :param usergroupids: IDs of the user groups to delete

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the deleted user groups.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_delete 28
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usergroup.delete'
            if not isinstance(usergroupids, list):
                usergroupids = [usergroupids]
            params = usergroupids
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['usrgrpids']
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_exists(name=None, node=None, nodeids=None, **connection_args):
    '''
    Checks if at least one user group that matches the given filter criteria exists

    .. versionadded:: 2016.3.0

    :param name: names of the user groups
    :param node: name of the node the user groups must belong to (This will override the nodeids parameter.)
    :param nodeids: IDs of the nodes the user groups must belong to

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: True if at least one user group that matches the given filter criteria exists, else False.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_exists Guests
    '''
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)
    try:
        if conn_args:
            # usergroup.exists deprecated
            if LooseVersion(zabbix_version) > LooseVersion("2.5"):
                if not name:
                    name = ''
                ret = usergroup_get(name, None, **connection_args)
                return bool(ret)
            # zabbix 2.4 nad earlier
            else:
                method = 'usergroup.exists'
                params = {}
                if not name and not node and not nodeids:
                    return {'result': False, 'comment': 'Please submit name, node or nodeids parameter to check if '
                                                        'at least one user group exists.'}
                if name:
                    params['name'] = name
                # deprecated in 2.4
                if LooseVersion(zabbix_version) < LooseVersion("2.4"):
                    if node:
                        params['node'] = node
                    if nodeids:
                        params['nodeids'] = nodeids
                ret = _query(method, params, conn_args['url'], conn_args['auth'])
                return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def usergroup_get(name=None, usrgrpids=None, userids=None, **connection_args):
    '''
    Retrieve user groups according to the given parameters.
    NOTE: This function accepts all usergroup_get properties: keyword argument names differ depending on your zabbix
    version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/usergroup/get

    .. versionadded:: 2016.3.0

    :param name: names of the user groups
    :param usrgrpids: return only user groups with the given IDs
    :param userids: return only user groups that contain the given users
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with convenient user groups details, False if no user group found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_get Guests
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usergroup.get'
            params = {"output": "extend", "filter": {}}
            if not name and not usrgrpids and not userids:
                return False
            if name:
                params['filter'].setdefault('name', name)
            if usrgrpids:
                params.setdefault('usrgrpids', usrgrpids)
            if userids:
                params.setdefault('userids', userids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])

            return False if len(ret['result']) < 1 else ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def usergroup_update(usrgrpid, **connection_args):
    '''
    Update existing user group.
    NOTE: This function accepts all standard user group properties: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/usergroup/object#user_group

    .. versionadded:: 2016.3.0

    :param usrgrpid: ID of the user group to update.
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the updated user group, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_update 8 name=guestsRenamed
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usergroup.update'
            params = {"usrgrpid": usrgrpid}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['usrgrpids']
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_list(**connection_args):
    '''
    Retrieve all enabled user groups.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with enabled user groups details, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_list
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usergroup.get'
            params = {"output": "extend", }
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def host_create(host, groups, interfaces, **connection_args):
    '''
    Create new host.
    NOTE: This function accepts all standard host properties: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    .. versionadded:: 2016.3.0

    :param host: technical name of the host
    :param groups: groupids of host groups to add the host to
    :param interfaces: interfaces to be created for the host
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)
    :param visible_name: string with visible name of the host, use 'visible_name' instead of 'name' parameter
    to not mess with value supplied from Salt sls file.

    return: ID of the created host.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.host_create technicalname 4
        interfaces='{type: 1, main: 1, useip: 1, ip: "192.168.3.1", dns: "", port: 10050}'
        visible_name='Host Visible Name'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'host.create'
            params = {"host": host}
            # Groups
            if not isinstance(groups, list):
                groups = [groups]
            grps = []
            for group in groups:
                grps.append({"groupid": group})
            params['groups'] = grps
            # Interfaces
            if not isinstance(interfaces, list):
                interfaces = [interfaces]
            params['interfaces'] = interfaces
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['hostids']
        else:
            raise KeyError
    except KeyError:
        return ret


def host_delete(hostids, **connection_args):
    '''
    Delete hosts.

    .. versionadded:: 2016.3.0

    :param hostids: Hosts (hostids) to delete.
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the deleted hosts.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_delete 10106
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'host.delete'
            if not isinstance(hostids, list):
                params = [hostids]
            else:
                params = hostids
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['hostids']
        else:
            raise KeyError
    except KeyError:
        return ret


def host_exists(host=None, hostid=None, name=None, node=None, nodeids=None, **connection_args):
    '''
    Checks if at least one host that matches the given filter criteria exists.

    .. versionadded:: 2016.3.0

    :param host: technical name of the host
    :param hostids: Hosts (hostids) to delete.
    :param name: visible name of the host
    :param node: name of the node the hosts must belong to (zabbix API < 2.4)
    :param nodeids: IDs of the node the hosts must belong to (zabbix API < 2.4)
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the deleted hosts, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_exists 'Zabbix server'
    '''
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)

    try:
        if conn_args:
            # hostgroup.exists deprecated
            if LooseVersion(zabbix_version) > LooseVersion("2.5"):
                if not host:
                    host = None
                if not name:
                    name = None
                if not hostid:
                    hostid = None
                ret = host_get(host, name, hostid, **connection_args)
                return bool(ret)
            # zabbix 2.4 nad earlier
            else:
                method = 'host.exists'
                params = {}
                if hostid:
                    params['hostid'] = hostid
                if host:
                    params['host'] = host
                if name:
                    params['name'] = name
                # deprecated in 2.4
                if LooseVersion(zabbix_version) < LooseVersion("2.4"):
                    if node:
                        params['node'] = node
                    if nodeids:
                        params['nodeids'] = nodeids
                if not hostid and not host and not name and not node and not nodeids:
                    return {'result': False, 'comment': 'Please submit hostid, host, name, node or nodeids parameter to'
                                                        'check if at least one host that matches the given filter '
                                                        'criteria exists.'}
                ret = _query(method, params, conn_args['url'], conn_args['auth'])
                return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def host_get(host=None, name=None, hostids=None, **connection_args):
    '''
    Retrieve hosts according to the given parameters.
    NOTE: This function accepts all optional host.get parameters: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/get

    .. versionadded:: 2016.3.0

    :param host: technical name of the host
    :param name: visible name of the host
    :param hostids: ids of the hosts
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)


    :return: Array with convenient hosts details, False if no host found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_get 'Zabbix server'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'host.get'
            params = {"output": "extend", "filter": {}}
            if not name and not hostids and not host:
                return False
            if name:
                params['filter'].setdefault('name', name)
            if hostids:
                params.setdefault('hostids', hostids)
            if host:
                params['filter'].setdefault('host', host)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result'] if len(ret['result']) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return False


def host_update(hostid, **connection_args):
    '''
    Update existing hosts.
    NOTE: This function accepts all standard host and host.update properties: keyword argument names differ depending
    on your zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/update
    https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    .. versionadded:: 2016.3.0

    :param hostid: ID of the host to update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)
    :param visible_name: string with visible name of the host, use 'visible_name' instead of 'name' parameter
    to not mess with value supplied from Salt sls file.

    :return: ID of the updated host.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_update 10084 name='Zabbix server2'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'host.update'
            params = {"hostid": hostid}
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['hostids']
        else:
            raise KeyError
    except KeyError:
        return ret


def host_list(**connection_args):
    '''
    Retrieve all hosts.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with details about hosts, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_list
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'host.get'
            params = {"output": "extend", }
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def hostgroup_create(name, **connection_args):
    '''
    Create a host group.
    NOTE: This function accepts all standard host group properties: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostgroup/object#host_group

    .. versionadded:: 2016.3.0

    :param name: name of the host group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the created host group.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_create MyNewGroup
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.create'
            params = {"name": name}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['groupids']
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_delete(hostgroupids, **connection_args):
    '''
    Delete the host group.

    .. versionadded:: 2016.3.0

    :param hostgroupids: IDs of the host groups to delete
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the deleted host groups, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_delete 23
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.delete'
            if not isinstance(hostgroupids, list):
                params = [hostgroupids]
            else:
                params = hostgroupids
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['groupids']
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_exists(name=None, groupid=None, node=None, nodeids=None, **connection_args):
    '''
    Checks if at least one host group that matches the given filter criteria exists.

    .. versionadded:: 2016.3.0

    :param name: names of the host groups
    :param groupid: host group IDs
    :param node: name of the node the host groups must belong to (zabbix API < 2.4)
    :param nodeids: IDs of the nodes the host groups must belong to (zabbix API < 2.4)
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: True if at least one host group exists, False if not or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_exists MyNewGroup
    '''
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)
    try:
        if conn_args:
            # hostgroup.exists deprecated
            if LooseVersion(zabbix_version) > LooseVersion("2.5"):
                if not groupid:
                    groupid = None
                if not name:
                    name = None
                ret = hostgroup_get(name, groupid, **connection_args)
                return bool(ret)
            # zabbix 2.4 nad earlier
            else:
                params = {}
                method = 'hostgroup.exists'
                if groupid:
                    params['groupid'] = groupid
                if name:
                    params['name'] = name
                # deprecated in 2.4
                if LooseVersion(zabbix_version) < LooseVersion("2.4"):
                    if node:
                        params['node'] = node
                    if nodeids:
                        params['nodeids'] = nodeids
                if not groupid and not name and not node and not nodeids:
                    return {'result': False, 'comment': 'Please submit groupid, name, node or nodeids parameter to'
                                                        'check if at least one host group that matches the given filter'
                                                        ' criteria exists.'}
                ret = _query(method, params, conn_args['url'], conn_args['auth'])
                return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def hostgroup_get(name=None, groupids=None, hostids=None, **connection_args):
    '''
    Retrieve host groups according to the given parameters.
    NOTE: This function accepts all standard hostgroup.get properities: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.2/manual/api/reference/hostgroup/get

    .. versionadded:: 2016.3.0

    :param name: names of the host groups
    :param groupid: host group IDs
    :param node: name of the node the host groups must belong to
    :param nodeids: IDs of the nodes the host groups must belong to
    :param hostids: return only host groups that contain the given hosts

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with host groups details, False if no convenient host group found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_get MyNewGroup
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.get'
            params = {"output": "extend"}
            if not groupids and not name and not hostids:
                return False
            if name:
                name_dict = {"name": name}
                params.setdefault('filter', name_dict)
            if groupids:
                params.setdefault('groupids', groupids)
            if hostids:
                params.setdefault('hostids', hostids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result'] if len(ret['result']) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return False


def hostgroup_update(groupid, name=None, **connection_args):
    '''
    Update existing hosts group.
    NOTE: This function accepts all standard host group properties: keyword argument names differ depending on your
    zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostgroup/object#host_group

    .. versionadded:: 2016.3.0

    :param groupid: ID of the host group to update
    :param name: name of the host group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of updated host groups.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_update 24 name='Renamed Name'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.update'
            params = {"groupid": groupid}
            if name:
                params['name'] = name
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['groupids']
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_list(**connection_args):
    '''
    Retrieve all host groups.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with details about host groups, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_list
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.get'
            params = {"output": "extend", }
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']
        else:
            raise KeyError
    except KeyError:
        return False


def hostinterface_get(hostids, **connection_args):
    '''
    Retrieve host groups according to the given parameters.
    NOTE: This function accepts all standard hostinterface.get properities: keyword argument names differ depending
    on your zabbix version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostinterface/get

    .. versionadded:: 2016.3.0

    :param hostids: Return only host interfaces used by the given hosts.
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with host interfaces details, False if no convenient host interfaces found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_get 101054
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostinterface.get'
            params = {"output": "extend"}
            if hostids:
                params.setdefault('hostids', hostids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result'] if len(ret['result']) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return False


def hostinterface_create(hostid, ip, dns='', main=1, type=1, useip=1, port=None, **connection_args):
    '''
    Create new host interface
    NOTE: This function accepts all standard host group interface: keyword argument names differ depending
    on your zabbix version, see: https://www.zabbix.com/documentation/3.0/manual/api/reference/hostinterface/object

    .. versionadded:: 2016.3.0

    :param hostid: ID of the host the interface belongs to
    :param ip: IP address used by the interface
    :param dns: DNS name used by the interface
    :param main: whether the interface is used as default on the host (0 - not default, 1 - default)
    :param port: port number used by the interface
    :param type: Interface type (1 - agent; 2 - SNMP; 3 - IPMI; 4 - JMX)
    :param useip: Whether the connection should be made via IP (0 - connect using host DNS name; 1 - connect using
    host IP address for this host interface)
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the created host interface, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_create 10105 192.193.194.197
    '''
    conn_args = _login(**connection_args)

    if not port:
        port = INTERFACE_DEFAULT_PORTS[type]

    try:
        if conn_args:
            method = 'hostinterface.create'
            params = {"hostid": hostid, "ip": ip, "dns": dns, "main": main, "port": port, "type": type, "useip": useip}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['interfaceids']
        else:
            raise KeyError
    except KeyError:
        return ret


def hostinterface_delete(interfaceids, **connection_args):
    '''
    Delete host interface

    .. versionadded:: 2016.3.0

    :param interfaceids: IDs of the host interfaces to delete
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of deleted host interfaces, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_delete 50
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostinterface.delete'
            if isinstance(interfaceids, list):
                params = interfaceids
            else:
                params = [interfaceids]
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['interfaceids']
        else:
            raise KeyError
    except KeyError:
        return ret


def hostinterface_update(interfaceid, **connection_args):
    '''
    Update host interface
    NOTE: This function accepts all standard hostinterface: keyword argument names differ depending on your zabbix
    version, see: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostinterface/object#host_interface

    .. versionadded:: 2016.3.0

    :param interfaceid: ID of the hostinterface to update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the updated host interface, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_update 6 ip=0.0.0.2
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostinterface.update'
            params = {"interfaceid": interfaceid}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['interfaceids']
        else:
            raise KeyError
    except KeyError:
        return ret
