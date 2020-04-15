# -*- coding: utf-8 -*-
"""
Support for Zabbix

:optdepends:    - zabbix server

:configuration: This module is not usable until the zabbix user and zabbix password are specified either in a pillar
    or in the minion's config file. Zabbix url should be also specified.

    .. code-block:: yaml

        zabbix.user: Admin
        zabbix.password: mypassword
        zabbix.url: http://127.0.0.1/zabbix/api_jsonrpc.php


    Connection arguments from the minion config file can be overridden on the CLI by using arguments with
    ``_connection_`` prefix.

    .. code-block:: bash

        zabbix.apiinfo_version _connection_user=Admin _connection_password=zabbix _connection_url=http://host/zabbix/

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import Python libs
import logging
import os
import socket

import salt.utils.data
import salt.utils.files
import salt.utils.http
import salt.utils.json
from salt.exceptions import SaltException

# Import Salt libs
from salt.ext import six

# pylint: disable=import-error,no-name-in-module,unused-import
from salt.ext.six.moves.urllib.error import HTTPError, URLError
from salt.utils.versions import LooseVersion as _LooseVersion

# pylint: enable=import-error,no-name-in-module,unused-import

log = logging.getLogger(__name__)

INTERFACE_DEFAULT_PORTS = [10050, 161, 623, 12345]

ZABBIX_TOP_LEVEL_OBJECTS = (
    "hostgroup",
    "template",
    "host",
    "maintenance",
    "action",
    "drule",
    "service",
    "proxy",
    "screen",
    "usergroup",
    "mediatype",
    "script",
    "valuemap",
)

# Zabbix object and its ID name mapping
ZABBIX_ID_MAPPER = {
    "action": "actionid",
    "alert": "alertid",
    "application": "applicationid",
    "dhost": "dhostid",
    "dservice": "dserviceid",
    "dcheck": "dcheckid",
    "drule": "druleid",
    "event": "eventid",
    "graph": "graphid",
    "graphitem": "gitemid",
    "graphprototype": "graphid",
    "history": "itemid",
    "host": "hostid",
    "hostgroup": "groupid",
    "hostinterface": "interfaceid",
    "hostprototype": "hostid",
    "iconmap": "iconmapid",
    "image": "imageid",
    "item": "itemid",
    "itemprototype": "itemid",
    "service": "serviceid",
    "discoveryrule": "itemid",
    "maintenance": "maintenanceid",
    "map": "sysmapid",
    "usermedia": "mediaid",
    "mediatype": "mediatypeid",
    "proxy": "proxyid",
    "screen": "screenid",
    "screenitem": "screenitemid",
    "script": "scriptid",
    "template": "templateid",
    "templatescreen": "screenid",
    "templatescreenitem": "screenitemid",
    "trend": "itemid",
    "trigger": "triggerid",
    "triggerprototype": "triggerid",
    "user": "userid",
    "usergroup": "usrgrpid",
    "usermacro": "globalmacroid",
    "valuemap": "valuemapid",
    "httptest": "httptestid",
}

# Define the module's virtual name
__virtualname__ = "zabbix"


def __virtual__():
    """
    Only load the module if all modules are imported correctly.
    """
    return __virtualname__


def _frontend_url():
    """
    Tries to guess the url of zabbix frontend.

    .. versionadded:: 2016.3.0
    """
    hostname = socket.gethostname()
    frontend_url = "http://" + hostname + "/zabbix/api_jsonrpc.php"
    try:
        try:
            response = salt.utils.http.query(frontend_url)
            error = response["error"]
        except HTTPError as http_e:
            error = six.text_type(http_e)
        if error.find("412: Precondition Failed"):
            return frontend_url
        else:
            raise KeyError
    except (ValueError, KeyError):
        return False


def _query(method, params, url, auth=None):
    """
    JSON request to Zabbix API.

    .. versionadded:: 2016.3.0

    :param method: actual operation to perform via the API
    :param params: parameters required for specific method
    :param url: url of zabbix api
    :param auth: auth token for zabbix api (only for methods with required authentication)

    :return: Response from API with desired data in JSON format. In case of error returns more specific description.

    .. versionchanged:: 2017.7
    """

    unauthenticated_methods = [
        "user.login",
        "apiinfo.version",
    ]

    header_dict = {"Content-type": "application/json"}
    data = {"jsonrpc": "2.0", "id": 0, "method": method, "params": params}

    if method not in unauthenticated_methods:
        data["auth"] = auth

    data = salt.utils.json.dumps(data)

    log.info(
        "_QUERY input:\nurl: %s\ndata: %s", six.text_type(url), six.text_type(data)
    )

    try:
        result = salt.utils.http.query(
            url,
            method="POST",
            data=data,
            header_dict=header_dict,
            decode_type="json",
            decode=True,
            status=True,
            headers=True,
        )
        log.info("_QUERY result: %s", six.text_type(result))
        if "error" in result:
            raise SaltException(
                "Zabbix API: Status: {0} ({1})".format(
                    result["status"], result["error"]
                )
            )
        ret = result.get("dict", {})
        if "error" in ret:
            raise SaltException(
                "Zabbix API: {} ({})".format(
                    ret["error"]["message"], ret["error"]["data"]
                )
            )
        return ret
    except ValueError as err:
        raise SaltException(
            "URL or HTTP headers are probably not correct! ({})".format(err)
        )
    except socket.error as err:
        raise SaltException("Check hostname in URL! ({})".format(err))


def _login(**kwargs):
    """
    Log in to the API and generate the authentication token.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: On success connargs dictionary with auth token and frontend url, False on failure.

    """
    connargs = dict()

    def _connarg(name, key=None):
        """
        Add key to connargs, only if name exists in our kwargs or, as zabbix.<name> in __opts__ or __pillar__

        Evaluate in said order - kwargs, opts, then pillar. To avoid collision with other functions,
        kwargs-based connection arguments are prefixed with 'connection_' (i.e. '_connection_user', etc.).

        Inspired by mysql salt module.
        """
        if key is None:
            key = name

        if name in kwargs:
            connargs[key] = kwargs[name]
        else:
            prefix = "_connection_"
            if name.startswith(prefix):
                try:
                    name = name[len(prefix) :]
                except IndexError:
                    return
            val = __salt__["config.option"]("zabbix.{0}".format(name), None)
            if val is not None:
                connargs[key] = val

    _connarg("_connection_user", "user")
    _connarg("_connection_password", "password")
    _connarg("_connection_url", "url")

    if "url" not in connargs:
        connargs["url"] = _frontend_url()

    try:
        if connargs["user"] and connargs["password"] and connargs["url"]:
            params = {"user": connargs["user"], "password": connargs["password"]}
            method = "user.login"
            ret = _query(method, params, connargs["url"])
            auth = ret["result"]
            connargs["auth"] = auth
            connargs.pop("user", None)
            connargs.pop("password", None)
            return connargs
        else:
            raise KeyError
    except KeyError as err:
        raise SaltException("URL is probably not correct! ({})".format(err))


def _params_extend(params, _ignore_name=False, **kwargs):
    """
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

    """
    # extend params value by optional zabbix API parameters
    for key in kwargs:
        if not key.startswith("_"):
            params.setdefault(key, kwargs[key])

    # ignore name parameter passed from Salt state module, use firstname or visible_name instead
    if _ignore_name:
        params.pop("name", None)
        if "firstname" in params:
            params["name"] = params.pop("firstname")
        elif "visible_name" in params:
            params["name"] = params.pop("visible_name")

    return params


def get_zabbix_id_mapper():
    """
    .. versionadded:: 2017.7

    Make ZABBIX_ID_MAPPER constant available to state modules.

    :return: ZABBIX_ID_MAPPER
    """
    return ZABBIX_ID_MAPPER


def substitute_params(input_object, extend_params=None, filter_key="name", **kwargs):
    """
    .. versionadded:: 2017.7

    Go through Zabbix object params specification and if needed get given object ID from Zabbix API and put it back
    as a value. Definition of the object is done via dict with keys "query_object" and "query_name".

    :param input_object: Zabbix object type specified in state file
    :param extend_params: Specify query with params
    :param filter_key: Custom filtering key (default: name)
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Params structure with values converted to string for further comparison purposes
    """
    if extend_params is None:
        extend_params = {}
    if isinstance(input_object, list):
        return [
            substitute_params(oitem, extend_params, filter_key, **kwargs)
            for oitem in input_object
        ]
    elif isinstance(input_object, dict):
        if "query_object" in input_object:
            query_params = {}
            if input_object["query_object"] not in ZABBIX_TOP_LEVEL_OBJECTS:
                query_params.update(extend_params)
            try:
                query_params.update(
                    {"filter": {filter_key: input_object["query_name"]}}
                )
                return get_object_id_by_params(
                    input_object["query_object"], query_params, **kwargs
                )
            except KeyError:
                raise SaltException(
                    "Qyerying object ID requested "
                    "but object name not provided: {0}".format(input_object)
                )
        else:
            return {
                key: substitute_params(val, extend_params, filter_key, **kwargs)
                for key, val in input_object.items()
            }
    else:
        # Zabbix response is always str, return everything in str as well
        return six.text_type(input_object)


# pylint: disable=too-many-return-statements,too-many-nested-blocks
def compare_params(defined, existing, return_old_value=False):
    """
    .. versionadded:: 2017.7

    Compares Zabbix object definition against existing Zabbix object.

    :param defined: Zabbix object definition taken from sls file.
    :param existing: Existing Zabbix object taken from result of an API call.
    :param return_old_value: Default False. If True, returns dict("old"=old_val, "new"=new_val) for rollback purpose.
    :return: Params that are different from existing object. Result extended by
        object ID can be passed directly to Zabbix API update method.
    """
    # Comparison of data types
    if not isinstance(defined, type(existing)):
        raise SaltException(
            "Zabbix object comparison failed (data type mismatch). Expecting {0}, got {1}. "
            'Existing value: "{2}", defined value: "{3}").'.format(
                type(existing), type(defined), existing, defined
            )
        )

    # Comparison of values
    if not salt.utils.data.is_iter(defined):
        if six.text_type(defined) != six.text_type(existing) and return_old_value:
            return {"new": six.text_type(defined), "old": six.text_type(existing)}
        elif six.text_type(defined) != six.text_type(existing) and not return_old_value:
            return six.text_type(defined)

    # Comparison of lists of values or lists of dicts
    if isinstance(defined, list):
        if len(defined) != len(existing):
            log.info("Different list length!")
            return {"new": defined, "old": existing} if return_old_value else defined
        else:
            difflist = []
            for ditem in defined:
                d_in_e = []
                for eitem in existing:
                    comp = compare_params(ditem, eitem, return_old_value)
                    if return_old_value:
                        d_in_e.append(comp["new"])
                    else:
                        d_in_e.append(comp)
                if all(d_in_e):
                    difflist.append(ditem)
            # If there is any difference in a list then whole defined list must be returned and provided for update
            if any(difflist) and return_old_value:
                return {"new": defined, "old": existing}
            elif any(difflist) and not return_old_value:
                return defined

    # Comparison of dicts
    if isinstance(defined, dict):
        try:
            # defined must be a subset of existing to be compared
            if set(defined) <= set(existing):
                intersection = set(defined) & set(existing)
                diffdict = {"new": {}, "old": {}} if return_old_value else {}
                for i in intersection:
                    comp = compare_params(defined[i], existing[i], return_old_value)
                    if return_old_value:
                        if comp or (not comp and isinstance(comp, list)):
                            diffdict["new"].update({i: defined[i]})
                            diffdict["old"].update({i: existing[i]})
                    else:
                        if comp or (not comp and isinstance(comp, list)):
                            diffdict.update({i: defined[i]})
                return diffdict

            return {"new": defined, "old": existing} if return_old_value else defined

        except TypeError:
            raise SaltException(
                "Zabbix object comparison failed (data type mismatch). Expecting {0}, got {1}. "
                'Existing value: "{2}", defined value: "{3}").'.format(
                    type(existing), type(defined), existing, defined
                )
            )


def get_object_id_by_params(obj, params=None, **connection_args):
    """
    .. versionadded:: 2017.7

    Get ID of single Zabbix object specified by its name.

    :param obj: Zabbix object type
    :param params: Parameters by which object is uniquely identified
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: object ID
    """
    if params is None:
        params = {}
    res = run_query(obj + ".get", params, **connection_args)
    if res and len(res) == 1:
        return six.text_type(res[0][ZABBIX_ID_MAPPER[obj]])
    else:
        raise SaltException(
            "Zabbix API: Object does not exist or bad Zabbix user permissions or other unexpected "
            "result. Called method {0} with params {1}. "
            "Result: {2}".format(obj + ".get", params, res)
        )


def apiinfo_version(**connection_args):
    """
    Retrieve the version of the Zabbix API.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: On success string with Zabbix API version, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.apiinfo_version
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "apiinfo.version"
            params = {}
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return False


def user_create(alias, passwd, usrgrps, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Create new zabbix user

    .. note::
        This function accepts all standard user properties: keyword argument
        names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.0/manual/appendix/api/user/definitions#user

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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.create"
            params = {"alias": alias, "passwd": passwd, "usrgrps": []}
            # User groups
            if not isinstance(usrgrps, list):
                usrgrps = [usrgrps]
            for usrgrp in usrgrps:
                params["usrgrps"].append({"usrgrpid": usrgrp})

            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["userids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def user_delete(users, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.delete"
            if not isinstance(users, list):
                params = [users]
            else:
                params = users

            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["userids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def user_exists(alias, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.get"
            params = {"output": "extend", "filter": {"alias": alias}}
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return True if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def user_get(alias=None, userids=None, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.get"
            params = {"output": "extend", "filter": {}}
            if not userids and not alias:
                return {
                    "result": False,
                    "comment": "Please submit alias or userids parameter to retrieve users.",
                }
            if alias:
                params["filter"].setdefault("alias", alias)
            if userids:
                params.setdefault("userids", userids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def user_update(userid, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Update existing users

    .. note::
        This function accepts all standard user properties: keyword argument
        names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.0/manual/appendix/api/user/definitions#user

    :param userid: id of the user to update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Id of the updated user on success.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_update 16 visible_name='James Brown'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.update"
            params = {
                "userid": userid,
            }
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["userids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def user_getmedia(userids=None, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Retrieve media according to the given parameters

    .. note::
        This function accepts all standard usermedia.get properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/3.2/manual/api/reference/usermedia/get

    :param userids: return only media that are used by the given users

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: List of retrieved media, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_getmedia
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usermedia.get"
            if userids:
                params = {"userids": userids}
            else:
                params = {}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def user_addmedia(
    userids, active, mediatypeid, period, sendto, severity, **connection_args
):
    """
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

    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.addmedia"
            params = {"users": []}
            # Users
            if not isinstance(userids, list):
                userids = [userids]
            for user in userids:
                params["users"].append({"userid": user})
            # Medias
            params["medias"] = [
                {
                    "active": active,
                    "mediatypeid": mediatypeid,
                    "period": period,
                    "sendto": sendto,
                    "severity": severity,
                },
            ]

            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["mediaids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def user_deletemedia(mediaids, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.deletemedia"

            if not isinstance(mediaids, list):
                mediaids = [mediaids]
            params = mediaids
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["mediaids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def user_list(**connection_args):
    """
    Retrieve all of the configured users.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with user details.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.user_list
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "user.get"
            params = {"output": "extend"}
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_create(name, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Create new user group

    .. note::
        This function accepts all standard user group properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.0/manual/appendix/api/usergroup/definitions#user_group

    :param name: name of the user group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return:  IDs of the created user groups.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_create GroupName
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usergroup.create"
            params = {"name": name}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["usrgrpids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_delete(usergroupids, **connection_args):
    """
    .. versionadded:: 2016.3.0

    :param usergroupids: IDs of the user groups to delete

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the deleted user groups.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_delete 28
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usergroup.delete"
            if not isinstance(usergroupids, list):
                usergroupids = [usergroupids]
            params = usergroupids
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["usrgrpids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_exists(name=None, node=None, nodeids=None, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)
    ret = False
    try:
        if conn_args:
            # usergroup.exists deprecated
            if _LooseVersion(zabbix_version) > _LooseVersion("2.5"):
                if not name:
                    name = ""
                ret = usergroup_get(name, None, **connection_args)
                return bool(ret)
            # zabbix 2.4 and earlier
            else:
                method = "usergroup.exists"
                params = {}
                if not name and not node and not nodeids:
                    return {
                        "result": False,
                        "comment": "Please submit name, node or nodeids parameter to check if "
                        "at least one user group exists.",
                    }
                if name:
                    params["name"] = name
                # deprecated in 2.4
                if _LooseVersion(zabbix_version) < _LooseVersion("2.4"):
                    if node:
                        params["node"] = node
                    if nodeids:
                        params["nodeids"] = nodeids
                ret = _query(method, params, conn_args["url"], conn_args["auth"])
                return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_get(name=None, usrgrpids=None, userids=None, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Retrieve user groups according to the given parameters

    .. note::
        This function accepts all usergroup_get properties: keyword argument
        names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/usergroup/get

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
    """
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usergroup.get"
            # Versions above 2.4 allow retrieving user group permissions
            if _LooseVersion(zabbix_version) > _LooseVersion("2.5"):
                params = {"selectRights": "extend", "output": "extend", "filter": {}}
            else:
                params = {"output": "extend", "filter": {}}
            if not name and not usrgrpids and not userids:
                return False
            if name:
                params["filter"].setdefault("name", name)
            if usrgrpids:
                params.setdefault("usrgrpids", usrgrpids)
            if userids:
                params.setdefault("userids", userids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])

            return False if len(ret["result"]) < 1 else ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_update(usrgrpid, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Update existing user group

    .. note::
        This function accepts all standard user group properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/usergroup/object#user_group

    :param usrgrpid: ID of the user group to update.
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the updated user group, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_update 8 name=guestsRenamed
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usergroup.update"
            params = {"usrgrpid": usrgrpid}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["usrgrpids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usergroup_list(**connection_args):
    """
    Retrieve all enabled user groups.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with enabled user groups details, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_list
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usergroup.get"
            params = {
                "output": "extend",
            }
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def host_create(host, groups, interfaces, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Create new host

    .. note::
        This function accepts all standard host properties: keyword argument
        names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    :param host: technical name of the host
    :param groups: groupids of host groups to add the host to
    :param interfaces: interfaces to be created for the host
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)
    :param visible_name: string with visible name of the host, use
        'visible_name' instead of 'name' parameter to not mess with value
        supplied from Salt sls file.

    return: ID of the created host.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.host_create technicalname 4
        interfaces='{type: 1, main: 1, useip: 1, ip: "192.168.3.1", dns: "", port: 10050}'
        visible_name='Host Visible Name' inventory_mode=0 inventory='{"alias": "something"}'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "host.create"
            params = {"host": host}
            # Groups
            if not isinstance(groups, list):
                groups = [groups]
            grps = []
            for group in groups:
                grps.append({"groupid": group})
            params["groups"] = grps
            # Interfaces
            if not isinstance(interfaces, list):
                interfaces = [interfaces]
            params["interfaces"] = interfaces
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["hostids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def host_delete(hostids, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "host.delete"
            if not isinstance(hostids, list):
                params = [hostids]
            else:
                params = hostids
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["hostids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def host_exists(
    host=None, hostid=None, name=None, node=None, nodeids=None, **connection_args
):
    """
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
    """
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)
    ret = False
    try:
        if conn_args:
            # hostgroup.exists deprecated
            if _LooseVersion(zabbix_version) > _LooseVersion("2.5"):
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
                method = "host.exists"
                params = {}
                if hostid:
                    params["hostid"] = hostid
                if host:
                    params["host"] = host
                if name:
                    params["name"] = name
                # deprecated in 2.4
                if _LooseVersion(zabbix_version) < _LooseVersion("2.4"):
                    if node:
                        params["node"] = node
                    if nodeids:
                        params["nodeids"] = nodeids
                if not hostid and not host and not name and not node and not nodeids:
                    return {
                        "result": False,
                        "comment": "Please submit hostid, host, name, node or nodeids parameter to"
                        "check if at least one host that matches the given filter "
                        "criteria exists.",
                    }
                ret = _query(method, params, conn_args["url"], conn_args["auth"])
                return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def host_get(host=None, name=None, hostids=None, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Retrieve hosts according to the given parameters

    .. note::
        This function accepts all optional host.get parameters: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/get

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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "host.get"
            params = {"output": "extend", "filter": {}}
            if not name and not hostids and not host:
                return False
            if name:
                params["filter"].setdefault("name", name)
            if hostids:
                params.setdefault("hostids", hostids)
            if host:
                params["filter"].setdefault("host", host)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def host_update(hostid, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Update existing hosts

    .. note::
        This function accepts all standard host and host.update properties:
        keyword argument names differ depending on your zabbix version, see the
        documentation for `host objects`_ and the documentation for `updating
        hosts`_.

        .. _`host objects`: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host
        .. _`updating hosts`: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/update

    :param hostid: ID of the host to update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)
    :param visible_name: string with visible name of the host, use
        'visible_name' instead of 'name' parameter to not mess with value
        supplied from Salt sls file.

    :return: ID of the updated host.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_update 10084 name='Zabbix server2'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "host.update"
            params = {"hostid": hostid}
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["hostids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def host_inventory_get(hostids, **connection_args):
    """
    Retrieve host inventory according to the given parameters.
    See: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host_inventory

    .. versionadded:: 2019.2.0

    :param hostids: Return only host interfaces used by the given hosts.
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with host interfaces details, False if no convenient host interfaces found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_inventory_get 101054
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "host.get"
            params = {"selectInventory": "extend"}
            if hostids:
                params.setdefault("hostids", hostids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return (
                ret["result"][0]["inventory"]
                if len(ret["result"][0]["inventory"]) > 0
                else False
            )
        else:
            raise KeyError
    except KeyError:
        return ret


def host_inventory_set(hostid, **connection_args):
    """
    Update host inventory items
    NOTE: This function accepts all standard host: keyword argument names for inventory
    see: https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host_inventory

    .. versionadded:: 2019.2.0

    :param hostid: ID of the host to update
    :param clear_old: Set to True in order to remove all existing inventory items before setting the specified items
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the updated host, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_inventory_set 101054 asset_tag=jml3322 type=vm clear_old=True
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            params = {}
            clear_old = False
            method = "host.update"

            if connection_args.get("clear_old"):
                clear_old = True

            connection_args.pop("clear_old", None)
            inventory_params = dict(_params_extend(params, **connection_args))
            for key in inventory_params:
                params.pop(key, None)

            if hostid:
                params.setdefault("hostid", hostid)
            if clear_old:
                # Set inventory to disabled in order to clear existing data
                params["inventory_mode"] = "-1"
                ret = _query(method, params, conn_args["url"], conn_args["auth"])

            # Set inventory mode to manual in order to submit inventory data
            params["inventory_mode"] = "0"
            params["inventory"] = inventory_params
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def host_list(**connection_args):
    """
    Retrieve all hosts.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with details about hosts, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.host_list
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "host.get"
            params = {
                "output": "extend",
            }
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_create(name, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Create a host group

    .. note::
        This function accepts all standard host group properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostgroup/object#host_group

    :param name: name of the host group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the created host group.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_create MyNewGroup
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostgroup.create"
            params = {"name": name}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["groupids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_delete(hostgroupids, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostgroup.delete"
            if not isinstance(hostgroupids, list):
                params = [hostgroupids]
            else:
                params = hostgroupids
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["groupids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_exists(
    name=None, groupid=None, node=None, nodeids=None, **connection_args
):
    """
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
    """
    conn_args = _login(**connection_args)
    zabbix_version = apiinfo_version(**connection_args)
    ret = False
    try:
        if conn_args:
            # hostgroup.exists deprecated
            if _LooseVersion(zabbix_version) > _LooseVersion("2.5"):
                if not groupid:
                    groupid = None
                if not name:
                    name = None
                ret = hostgroup_get(name, groupid, **connection_args)
                return bool(ret)
            # zabbix 2.4 nad earlier
            else:
                params = {}
                method = "hostgroup.exists"
                if groupid:
                    params["groupid"] = groupid
                if name:
                    params["name"] = name
                # deprecated in 2.4
                if _LooseVersion(zabbix_version) < _LooseVersion("2.4"):
                    if node:
                        params["node"] = node
                    if nodeids:
                        params["nodeids"] = nodeids
                if not groupid and not name and not node and not nodeids:
                    return {
                        "result": False,
                        "comment": "Please submit groupid, name, node or nodeids parameter to"
                        "check if at least one host group that matches the given filter"
                        " criteria exists.",
                    }
                ret = _query(method, params, conn_args["url"], conn_args["auth"])
                return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_get(name=None, groupids=None, hostids=None, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Retrieve host groups according to the given parameters

    .. note::
        This function accepts all standard hostgroup.get properities: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.2/manual/api/reference/hostgroup/get

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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostgroup.get"
            params = {"output": "extend"}
            if not groupids and not name and not hostids:
                return False
            if name:
                name_dict = {"name": name}
                params.setdefault("filter", name_dict)
            if groupids:
                params.setdefault("groupids", groupids)
            if hostids:
                params.setdefault("hostids", hostids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_update(groupid, name=None, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Update existing hosts group

    .. note::
        This function accepts all standard host group properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostgroup/object#host_group

    :param groupid: ID of the host group to update
    :param name: name of the host group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of updated host groups.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_update 24 name='Renamed Name'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostgroup.update"
            params = {"groupid": groupid}
            if name:
                params["name"] = name
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["groupids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostgroup_list(**connection_args):
    """
    Retrieve all host groups.

    .. versionadded:: 2016.3.0

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with details about host groups, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostgroup_list
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostgroup.get"
            params = {
                "output": "extend",
            }
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostinterface_get(hostids, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Retrieve host groups according to the given parameters

    .. note::
        This function accepts all standard hostinterface.get properities:
        keyword argument names differ depending on your zabbix version, see
        here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostinterface/get

    :param hostids: Return only host interfaces used by the given hosts.

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)

    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)

    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: Array with host interfaces details, False if no convenient host interfaces found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_get 101054
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostinterface.get"
            params = {"output": "extend"}
            if hostids:
                params.setdefault("hostids", hostids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def hostinterface_create(
    hostid, ip_, dns="", main=1, if_type=1, useip=1, port=None, **connection_args
):
    """
    .. versionadded:: 2016.3.0

    Create new host interface

    .. note::
        This function accepts all standard host group interface: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/3.0/manual/api/reference/hostinterface/object

    :param hostid: ID of the host the interface belongs to

    :param ip_: IP address used by the interface

    :param dns: DNS name used by the interface

    :param main: whether the interface is used as default on the host (0 - not default, 1 - default)

    :param port: port number used by the interface

    :param type: Interface type (1 - agent; 2 - SNMP; 3 - IPMI; 4 - JMX)

    :param useip: Whether the connection should be made via IP (0 - connect
        using host DNS name; 1 - connect using host IP address for this host
        interface)

    :param _connection_user: Optional - zabbix user (can also be set in opts or
        pillar, see module's docstring)

    :param _connection_password: Optional - zabbix password (can also be set in
        opts or pillar, see module's docstring)

    :param _connection_url: Optional - url of zabbix frontend (can also be set
        in opts, pillar, see module's docstring)

    :return: ID of the created host interface, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_create 10105 192.193.194.197
    """
    conn_args = _login(**connection_args)
    ret = False

    if not port:
        port = INTERFACE_DEFAULT_PORTS[if_type]

    try:
        if conn_args:
            method = "hostinterface.create"
            params = {
                "hostid": hostid,
                "ip": ip_,
                "dns": dns,
                "main": main,
                "port": port,
                "type": if_type,
                "useip": useip,
            }
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["interfaceids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostinterface_delete(interfaceids, **connection_args):
    """
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
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostinterface.delete"
            if isinstance(interfaceids, list):
                params = interfaceids
            else:
                params = [interfaceids]
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["interfaceids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def hostinterface_update(interfaceid, **connection_args):
    """
    .. versionadded:: 2016.3.0

    Update host interface

    .. note::
        This function accepts all standard hostinterface: keyword argument
        names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/2.4/manual/api/reference/hostinterface/object#host_interface

    :param interfaceid: ID of the hostinterface to update

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)

    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)

    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of the updated host interface, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.hostinterface_update 6 ip_=0.0.0.2
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "hostinterface.update"
            params = {"interfaceid": interfaceid}
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["interfaceids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_get(
    macro=None,
    hostids=None,
    templateids=None,
    hostmacroids=None,
    globalmacroids=None,
    globalmacro=False,
    **connection_args
):
    """
    Retrieve user macros according to the given parameters.

    Args:
        macro:          name of the usermacro
        hostids:        Return macros for the given hostids
        templateids:    Return macros for the given templateids
        hostmacroids:   Return macros with the given hostmacroids
        globalmacroids: Return macros with the given globalmacroids (implies globalmacro=True)
        globalmacro:    if True, returns only global macros


        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

    Returns:
        Array with usermacro details, False if no usermacro found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usermacro_get macro='{$SNMP_COMMUNITY}'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usermacro.get"
            params = {"output": "extend", "filter": {}}
            if macro:
                # Python mistakenly interprets macro names starting and ending with '{' and '}' as a dict
                if isinstance(macro, dict):
                    macro = "{" + six.text_type(macro.keys()[0]) + "}"
                if not macro.startswith("{") and not macro.endswith("}"):
                    macro = "{" + macro + "}"
                params["filter"].setdefault("macro", macro)
            if hostids:
                params.setdefault("hostids", hostids)
            elif templateids:
                params.setdefault("templateids", hostids)
            if hostmacroids:
                params.setdefault("hostmacroids", hostmacroids)
            elif globalmacroids:
                globalmacro = True
                params.setdefault("globalmacroids", globalmacroids)
            if globalmacro:
                params = _params_extend(params, globalmacro=True)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_create(macro, value, hostid, **connection_args):
    """
    Create new host usermacro.

    :param macro: name of the host usermacro
    :param value: value of the host usermacro
    :param hostid: hostid or templateid
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: ID of the created host usermacro.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.usermacro_create '{$SNMP_COMMUNITY}' 'public' 1
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            params = {}
            method = "usermacro.create"
            if macro:
                # Python mistakenly interprets macro names starting and ending with '{' and '}' as a dict
                if isinstance(macro, dict):
                    macro = "{" + six.text_type(macro.keys()[0]) + "}"
                if not macro.startswith("{") and not macro.endswith("}"):
                    macro = "{" + macro + "}"
                params["macro"] = macro
            params["value"] = value
            params["hostid"] = hostid
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["hostmacroids"][0]
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_createglobal(macro, value, **connection_args):
    """
    Create new global usermacro.

    :param macro: name of the global usermacro
    :param value: value of the global usermacro
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: ID of the created global usermacro.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.usermacro_createglobal '{$SNMP_COMMUNITY}' 'public'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            params = {}
            method = "usermacro.createglobal"
            if macro:
                # Python mistakenly interprets macro names starting and ending with '{' and '}' as a dict
                if isinstance(macro, dict):
                    macro = "{" + six.text_type(macro.keys()[0]) + "}"
                if not macro.startswith("{") and not macro.endswith("}"):
                    macro = "{" + macro + "}"
                params["macro"] = macro
            params["value"] = value
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["globalmacroids"][0]
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_delete(macroids, **connection_args):
    """
    Delete host usermacros.

    :param macroids: macroids of the host usermacros

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: IDs of the deleted host usermacro.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.usermacro_delete 21
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usermacro.delete"
            if isinstance(macroids, list):
                params = macroids
            else:
                params = [macroids]
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["hostmacroids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_deleteglobal(macroids, **connection_args):
    """
    Delete global usermacros.

    :param macroids: macroids of the global usermacros

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: IDs of the deleted global usermacro.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.usermacro_deleteglobal 21
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "usermacro.deleteglobal"
            if isinstance(macroids, list):
                params = macroids
            else:
                params = [macroids]
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["globalmacroids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_update(hostmacroid, value, **connection_args):
    """
    Update existing host usermacro.

    :param hostmacroid: id of the host usermacro
    :param value: new value of the host usermacro
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: ID of the update host usermacro.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.usermacro_update 1 'public'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            params = {}
            method = "usermacro.update"
            params["hostmacroid"] = hostmacroid
            params["value"] = value
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["hostmacroids"][0]
        else:
            raise KeyError
    except KeyError:
        return ret


def usermacro_updateglobal(globalmacroid, value, **connection_args):
    """
    Update existing global usermacro.

    :param globalmacroid: id of the host usermacro
    :param value: new value of the host usermacro
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: ID of the update global usermacro.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.usermacro_updateglobal 1 'public'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            params = {}
            method = "usermacro.updateglobal"
            params["globalmacroid"] = globalmacroid
            params["value"] = value
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["globalmacroids"][0]
        else:
            raise KeyError
    except KeyError:
        return ret


def mediatype_get(name=None, mediatypeids=None, **connection_args):
    """
    Retrieve mediatypes according to the given parameters.

    Args:
        name:         Name or description of the mediatype
        mediatypeids: ids of the mediatypes

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all optional mediatype.get parameters: keyword argument names depends on your zabbix version, see:

                https://www.zabbix.com/documentation/2.2/manual/api/reference/mediatype/get

    Returns:
        Array with mediatype details, False if no mediatype found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.mediatype_get name='Email'
        salt '*' zabbix.mediatype_get mediatypeids="['1', '2', '3']"
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "mediatype.get"
            params = {"output": "extend", "filter": {}}
            if name:
                params["filter"].setdefault("description", name)
            if mediatypeids:
                params.setdefault("mediatypeids", mediatypeids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def mediatype_create(name, mediatype, **connection_args):
    """
    Create new mediatype

    .. note::
        This function accepts all standard mediatype properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/3.0/manual/api/reference/mediatype/object

    :param mediatype: media type - 0: email, 1: script, 2: sms, 3: Jabber, 100: Ez Texting
    :param exec_path: exec path - Required for script and Ez Texting types, see Zabbix API docs
    :param gsm_modem: exec path - Required for sms type, see Zabbix API docs
    :param smtp_email: email address from which notifications will be sent, required for email type
    :param smtp_helo: SMTP HELO, required for email type
    :param smtp_server: SMTP server, required for email type
    :param status: whether the media type is enabled - 0: enabled, 1: disabled
    :param username: authentication user, required for Jabber and Ez Texting types
    :param passwd: authentication password, required for Jabber and Ez Texting types
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    return: ID of the created mediatype.

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.mediatype_create 'Email' 0 smtp_email='noreply@example.com'
        smtp_server='mailserver.example.com' smtp_helo='zabbix.example.com'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "mediatype.create"
            params = {"description": name}
            params["type"] = mediatype
            params = _params_extend(params, _ignore_name=True, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["mediatypeid"]
        else:
            raise KeyError
    except KeyError:
        return ret


def mediatype_delete(mediatypeids, **connection_args):
    """
    Delete mediatype


    :param interfaceids: IDs of the mediatypes to delete
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: ID of deleted mediatype, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.mediatype_delete 3
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "mediatype.delete"
            if isinstance(mediatypeids, list):
                params = mediatypeids
            else:
                params = [mediatypeids]
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["mediatypeids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def mediatype_update(mediatypeid, name=False, mediatype=False, **connection_args):
    """
    Update existing mediatype

    .. note::
        This function accepts all standard mediatype properties: keyword
        argument names differ depending on your zabbix version, see here__.

        .. __: https://www.zabbix.com/documentation/3.0/manual/api/reference/mediatype/object

    :param mediatypeid: ID of the mediatype to update
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    :return: IDs of the updated mediatypes, False on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.usergroup_update 8 name="Email update"
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "mediatype.update"
            params = {"mediatypeid": mediatypeid}
            if name:
                params["description"] = name
            if mediatype:
                params["type"] = mediatype
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"]["mediatypeids"]
        else:
            raise KeyError
    except KeyError:
        return ret


def template_get(name=None, host=None, templateids=None, **connection_args):
    """
    Retrieve templates according to the given parameters.

    Args:
        host: technical name of the template
        name: visible name of the template
        hostids: ids of the templates

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all optional template.get parameters: keyword argument names depends on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/template/get

    Returns:
        Array with convenient template details, False if no template found or on failure.

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.template_get name='Template OS Linux'
        salt '*' zabbix.template_get templateids="['10050', '10001']"
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            method = "template.get"
            params = {"output": "extend", "filter": {}}
            if name:
                params["filter"].setdefault("name", name)
            if host:
                params["filter"].setdefault("host", host)
            if templateids:
                params.setdefault("templateids", templateids)
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            return ret["result"] if len(ret["result"]) > 0 else False
        else:
            raise KeyError
    except KeyError:
        return ret


def run_query(method, params, **connection_args):
    """
    Send Zabbix API call

    Args:
        method: actual operation to perform via the API
        params: parameters required for specific method

        optional connection_args:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                all optional template.get parameters: keyword argument names depends on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/

    Returns:
        Response from Zabbix API

    CLI Example:
    .. code-block:: bash

        salt '*' zabbix.run_query proxy.create '{"host": "zabbixproxy.domain.com", "status": "5"}'
    """
    conn_args = _login(**connection_args)
    ret = False
    try:
        if conn_args:
            params = _params_extend(params, **connection_args)
            ret = _query(method, params, conn_args["url"], conn_args["auth"])
            if isinstance(ret["result"], bool):
                return ret["result"]
            if ret["result"] is True or len(ret["result"]) > 0:
                return ret["result"]
            else:
                return False
        else:
            raise KeyError
    except KeyError:
        return ret


def configuration_import(config_file, rules=None, file_format="xml", **connection_args):
    """
    .. versionadded:: 2017.7

    Imports Zabbix configuration specified in file to Zabbix server.

    :param config_file: File with Zabbix config (local or remote)
    :param rules: Optional - Rules that have to be different from default (defaults are the same as in Zabbix web UI.)
    :param file_format: Config file format (default: xml)
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    CLI Example:

    .. code-block:: bash

        salt '*' zabbix.configuration_import salt://zabbix/config/zabbix_templates.xml \
        "{'screens': {'createMissing': True, 'updateExisting': True}}"
    """
    if rules is None:
        rules = {}
    default_rules = {
        "applications": {
            "createMissing": True,
            "updateExisting": False,
            "deleteMissing": False,
        },
        "discoveryRules": {
            "createMissing": True,
            "updateExisting": True,
            "deleteMissing": False,
        },
        "graphs": {
            "createMissing": True,
            "updateExisting": True,
            "deleteMissing": False,
        },
        "groups": {"createMissing": True},
        "hosts": {"createMissing": False, "updateExisting": False},
        "images": {"createMissing": False, "updateExisting": False},
        "items": {
            "createMissing": True,
            "updateExisting": True,
            "deleteMissing": False,
        },
        "maps": {"createMissing": False, "updateExisting": False},
        "screens": {"createMissing": False, "updateExisting": False},
        "templateLinkage": {"createMissing": True},
        "templates": {"createMissing": True, "updateExisting": True},
        "templateScreens": {
            "createMissing": True,
            "updateExisting": True,
            "deleteMissing": False,
        },
        "triggers": {
            "createMissing": True,
            "updateExisting": True,
            "deleteMissing": False,
        },
        "valueMaps": {"createMissing": True, "updateExisting": False},
    }
    new_rules = dict(default_rules)

    if rules:
        for rule in rules:
            if rule in new_rules:
                new_rules[rule].update(rules[rule])
            else:
                new_rules[rule] = rules[rule]
    if "salt://" in config_file:
        tmpfile = salt.utils.files.mkstemp()
        cfile = __salt__["cp.get_file"](config_file, tmpfile)
        if not cfile or os.path.getsize(cfile) == 0:
            return {
                "name": config_file,
                "result": False,
                "message": "Failed to fetch config file.",
            }
    else:
        cfile = config_file
        if not os.path.isfile(cfile):
            return {
                "name": config_file,
                "result": False,
                "message": "Invalid file path.",
            }

    with salt.utils.files.fopen(cfile, mode="r") as fp_:
        xml = fp_.read()

    if "salt://" in config_file:
        salt.utils.files.safe_rm(cfile)

    params = {"format": file_format, "rules": new_rules, "source": xml}
    log.info("CONFIGURATION IMPORT: rules: %s", six.text_type(params["rules"]))
    try:
        run_query("configuration.import", params, **connection_args)
        return {
            "name": config_file,
            "result": True,
            "message": 'Zabbix API "configuration.import" method '
            "called successfully.",
        }
    except SaltException as exc:
        return {"name": config_file, "result": False, "message": six.text_type(exc)}
