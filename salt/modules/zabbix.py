# -*- coding: utf-8 -*-
'''
Support for Zabbix

:configuration: This module is not usable until the zabbix user and zabbix password are specified either in a pillar
    or in the minion's config file. Zabbix url should be also specified.

    For example::

        zabbix.user: Admin
        zabbix.password: mypassword
        zabbix.url: http://127.0.0.1/zabbix/api_jsonrpc.php


    Connection arguments from the minion config file can be overridden on the CLI by using arguments with
    _connection_ prefix.

    For example::

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


def __virtual__():
    '''
    Only load the module if Zabbix server is installed
    '''
    if salt.utils.which('zabbix_server'):
        return 'zabbix'
    return False


def _frontend_url():
    '''
    Tries to guess the url of zabbix frontend.
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

    Args:
        method: actual operation to perform via the API
        params: parameters required for specific method
        url: url of zabbix api
        auth: auth token for zabbix api (only for methods with required authentication)

    Returns:
        Response from API with desired data in JSON format.
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

    Args:
        optional kwargs:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        On success connargs dictionary with auth token and frontend url,
        False on failure.

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

    Args:
        params: Dictionary with parameters for zabbix API.
        _ignore_name: Salt State module is passing first line as 'name' parameter. If API uses optional parameter
                      'name' (for ex. host_create, user_create method), please use 'visible_name' or 'firstname'
                      instead of 'name' to not mess these values.
        optional kwargs:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)
                optional zabbix API parameters (see docstring of each function and zabbix API documentation)

    Returns:
        Extended params dictionary with parameters.

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

    Args:
        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)
    Returns:
        On success string with Zabbix API version, False on failure.

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

    Args:
        alias: user alias
        passwd: user's password
        usrgrps: user groups to add the user to

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                firstname: string with firstname of the user, use 'firstname' instead of 'name' parameter to not mess
                            with value supplied from Salt sls file.

                all standard user properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.0/manual/appendix/api/user/definitions#user

    Returns:
        On success string with id of the created user, False on failure.

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
        return False


def user_delete(users, **connection_args):
    '''
    Delete zabbix users.

    Args:
        users: array of users (userids) to delete

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        On success array with userids of deleted users, False on failure.

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
        return False


def user_exists(alias, **connection_args):
    '''
    Checks if user with given alias exists.

    Args:
        alias: user alias

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        True if user exists, else False.

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

    Args:
        alias: user alias
        userids: return only users with the given IDs

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        Array with details of convenient users, False on failure of if no user found.

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
    Update existing users.

    Args:
        userid: id of the user to update

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all standard user properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.0/manual/appendix/api/user/definitions#user

    Returns:
        Id of the updated user, False on failure.

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
        return False


def user_addmedia(users, medias, **connection_args):
    '''
    Add new media to multiple users.

    Args:
        users: Users (userids) to add the media to.
        madias: media to create for the given users

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        IDs of the created media, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_addmedia 16
        medias='{mediatypeid: 1, sendto: "support@example.com", active: 0, severity: 63, period: "1-7,00:00-24:00"}'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.addmedia'
            params = {"users": []}
            # Users
            if not isinstance(users, list):
                users = [users]
            for user in users:
                params['users'].append({"userid": user})
            # Medias
            if not isinstance(medias, list):
                medias = [medias]
            params['medias'] = medias

            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['mediaids']
        else:
            raise KeyError
    except KeyError:
        return False


def user_updatemedia(users, medias, **connection_args):
    '''
    Update media for multiple users.

    Args:
        users: Users (userids) to update.
        madias: Media to replace existing media. If a media has the mediaid property defined it will be updated,
                otherwise a new media will be created.

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        IDs of the updated users, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_updatemedia 17
        medias='{mediaid: 24, mediatypeid: 1, sendto: "support_new@example.com", active: 0,
        severity: 63, period: "1-7,00:00-24:00"}'
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'user.updatemedia'
            params = {"users": []}
            if not isinstance(users, list):
                users = [users]
            for user in users:
                params['users'].append({"userid": user})
            # Medias
            if not isinstance(medias, list):
                medias = [medias]
            params['medias'] = medias
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['userids']
        else:
            raise KeyError
    except KeyError:
        return False


def user_deletemedia(mediaids, **connection_args):
    '''
    Delete media by id.

    Args:
        mediaids: IDs of the media to delete

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        IDs of the deleted media, False on failure.

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
        return False


def user_list(**connection_args):
    '''
    Retrieve all of the configured users.

    Args:
        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        Array with user details, False on failure.

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
        return False


def usergroup_create(name, **connection_args):
    '''
    Create new user group.

    Args:
        name: name of the user group

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all standard user group properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.0/manual/appendix/api/usergroup/definitions#user_group

    Returns:
        IDs of the created user groups, False on failure.

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
        return False


def usergroup_delete(usergroupids, **connection_args):
    '''
    Delete user groups by id.

    Args:
        usergroupids: IDs of the user groups to delete

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        IDs of the deleted user groups, False on failure.

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
        return False


def usergroup_exists(name=None, node=None, nodeids=None, **connection_args):
    '''
    Checks if at least one user group that matches the given filter criteria exists

    Args:
        name: names of the user groups
        node: name of the node the user groups must belong to (This will override the nodeids parameter.)
        nodeids: IDs of the nodes the user groups must belong to

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        True if at least one user group that matches the given filter criteria exists, else False.

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


def usergroup_get(name=None, usrgrpids=None, **connection_args):
    '''
    Retrieve user groups according to the given parameters.

    Args:
        name: names of the user groups
        usrgrpids: return only user groups with the given IDs

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all usergroup_get properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/usergroup/get

    Returns:
        Array with convenient user groups details, False if no user group found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_get Guests
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'usergroup.get'
            params = {"output": "extend", "filter": {}}
            if not name and not usrgrpids:
                return False
            if name:
                params['filter'].setdefault('name', name)
            if usrgrpids:
                params.setdefault('usrgrpids', usrgrpids)
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

    Args:
        usrgrpid: ID of the user group to update.

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all standard user group properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/usergroup/object#user_group

    Returns:
        IDs of the updated user group, False on failure.

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
        return False


def usergroup_list(**connection_args):
    '''
    Retrieve all enabled user groups.

    Args:
            optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        Array with enabled user groups details, False on failure.

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

    Args:
        host: technical name of the host
        groups: groupids of host groups to add the host to
        interfaces: interfaces to be created for the host

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                visible_name: string with visible name of the host, use 'visible_name' instead of 'name' parameter
                              to not mess with value supplied from Salt sls file.

                all standard host properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    Returns:
        ID of the created host, False on failure.

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
        return False


def host_delete(hostids, **connection_args):
    '''
    Delete hosts.

    Args:
        hostids: Hosts (hostids) to delete.

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        IDs of the deleted hosts, False on failure.

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
        return False


def host_exists(host=None, hostid=None, name=None, node=None, nodeids=None, **connection_args):
    '''
    Checks if at least one host that matches the given filter criteria exists.

    Args:
        host: technical name of the host
        hostids: Hosts (hostids) to delete.
        name: visible name of the host
        node: name of the node the hosts must belong to (zabbix API < 2.4)
        nodeids: IDs of the node the hosts must belong to (zabbix API < 2.4)

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        IDs of the deleted hosts, False on failure.

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

    Args:
        host: technical name of the host
        name: visible name of the host
        hostids: ids of the hosts

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all optional host.get parameters: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/host/get

    Returns:
        Array with convenient hosts details, False if no host found or on failure.

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

    Args:
        hostid: ID of the host to update

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                visible_name: string with visible name of the host, use 'visible_name' instead of 'name' parameter
                              to not mess with value supplied from Salt sls file.

                all standard host and host.update properties: keyword argument names differ depending on
                your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/host/update
                https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    Returns:
        ID of the updated host, False on failure.

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
        return False


def host_list(**connection_args):
    '''
    Retrieve all hosts.

    optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        Array with details about hosts, False on failure.

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

    Args:
        name: name of the host group

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all standard host group properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/hostgroup/object#host_group

    Returns:
        ID of the created host group, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_create MyNewGroup
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.create'
            params = {"name": name}
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['groupids']
        else:
            raise KeyError
    except KeyError:
        return False


def hostgroup_delete(hostgroupids, **connection_args):
    '''
    Delete the host group.

    Args:
        hostgroupids: IDs of the host groups to delete

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        ID of the deleted host groups, False on failure.

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
        return False


def hostgroup_exists(name=None, groupid=None, node=None, nodeids=None, **connection_args):
    '''
    Checks if at least one host group that matches the given filter criteria exists.

    Args:
        name: names of the host groups
        groupid: host group IDs
        node: name of the node the host groups must belong to (zabbix API < 2.4)
        nodeids: IDs of the nodes the host groups must belong to (zabbix API < 2.4)

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        True if at least one host group exists, False if not or on failure.

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


def hostgroup_get(name=None, groupids=None, **connection_args):
    '''
    Retrieve host groups according to the given parameters.

    Args:
        name: names of the host groups
        groupid: host group IDs
        node: name of the node the host groups must belong to
        nodeids: IDs of the nodes the host groups must belong to

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all standard hostgroup.get properities: keyword argument names differ
                depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.2/manual/api/reference/hostgroup/get

    Returns:
        Array with host groups details, False if no convenient host group found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_get MyNewGroup
    '''
    conn_args = _login(**connection_args)
    try:
        if conn_args:
            method = 'hostgroup.get'
            params = {"output": "extend"}
            if not groupids and not name:
                return False
            if name:
                name_dict = {"name": name}
                params.setdefault('filter', name_dict)
            if groupids:
                params.setdefault('groupids', groupids)
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

    Args:
        groupid: ID of the host group to update
        name: name of the host group

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all standard host group properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/hostgroup/object#host_group

    Returns:
        IDs of updated host groups, False on failure.

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
            ret = _query(method, params, conn_args['url'], conn_args['auth'])
            return ret['result']['groupids']
        else:
            raise KeyError
    except KeyError:
        return False


def hostgroup_list(**connection_args):
    '''
    Retrieve all host groups.

    Args:
        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        Array with details about host groups, False on failure.

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
