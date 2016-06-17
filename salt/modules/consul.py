# -*- coding: utf-8 -*-
'''
Interact with Consul

https://www.consul.io

Configure the consul endpoint and token on the minion

  .. code-block:: yaml

    consul:
      - url: http://127.0.0.1:8500
      - token: secret

'''

# Import Python Libs
from __future__ import absolute_import

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
from salt.ext.six.moves.urllib.parse import quote as urlquote
from salt.exceptions import SaltInvocationError
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module

# Import salt libs
import salt.utils.http

import base64
import json

import logging
log = logging.getLogger(__name__)


# Don't shadow built-ins.
__func_alias__ = {
    'list_': 'list',
}

__virtualname__ = 'consul'


def _get_config():
    '''
    Retrieve Consul configuration
    '''
    return __salt__['config.get']('consul.url') or \
        __salt__['config.get']('consul:url')


def _get_token():
    '''
    Get API Token
    '''
    return __salt__['config.get']('consul.token') or \
        __salt__['config.get']('consul:token')


def _query(function,
           method='GET',
           api_version='v1',
           data=None,
           query_params=None):
    '''
    Consul object method function to construct and execute on the API URL.

    :param api_version  The Consul api version
    :param function:    The Consul api function to perform.
    :param method:      The HTTP method, e.g. GET or POST.
    :param data:        The data to be sent for POST method.
    :return:            The json response from the API call or False.
    '''
    headers = {}
    ret = {'comment': '', 'result': False}

    token = _get_token()

    if token:
        headers['X-Consul-Token'] = token

    if query_params is None:
        query_params = {}

    consul_url = _get_config()

    if not consul_url:
        log.error('No Consul URL found.')
        ret['comment'] = 'No Consul URL found.'
        return ret

    base_url = _urljoin(consul_url, '{0}/'.format(api_version))
    url = _urljoin(base_url, function, False)

    if data is None:
        data = {}

    data = json.dumps(data)

    result = salt.utils.http.query(
        url,
        method=method,
        params=query_params,
        data=data,
        decode=True,
        status=True,
        header_dict=headers,
        opts=__opts__,
    )

    if result['status'] == salt.ext.six.moves.http_client.OK:
        ret['comment'] = result.get('dict', 'OK')
        ret['result'] = True
    elif result['status'] == salt.ext.six.moves.http_client.NO_CONTENT:
        ret['comment'] = 'No content'
    elif result['status'] == salt.ext.six.moves.http_client.NOT_FOUND:
        ret['comment'] = 'Key not found.'
    else:
        if result:
            ret['comment'] = result['error']

    return ret


def list_(key=None, recurse=False):
    '''
    List keys in Consul

    :param key: The key to use as the starting point for the list.
    :param recurse: Return all keys with the given key prefix
    :return: The list of keys.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.list

        salt '*' consul.list key='web'

    '''
    query_params = {'keys': 'True'}

    if recurse:
        query_params['recurse'] = 'True'

    if key:
        function = 'kv/{0}'.format(key)
    else:
        query_params['recurse'] = 'True'
        function = 'kv/'

    return _query(
        function=function,
        query_params=query_params
    )


def get(key, recurse=False, decode=True, raw=False):
    '''
    Get key from Consul

    :param key: The key to use as the starting point for the list.
    :param recurse: Return values recursively beginning at the value of key.
    :param decode: By default values are stored as Base64 encoded values,
                   decode will return the whole key with the value decoded.
    :param raw: Simply return the decoded value of the key.
    :return: The keys in Consul.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.get key='web/key1'

        salt '*' consul.get key='web' recurse='True'

        salt '*' consul.get key='web' recurse='True' decode='False'

    By default values stored in Consul are base64 encoded, decoding these values
    is enabled by default

    .. code-block:: bash

        salt '*' consul.get key='web' recurse='True' decode='True' raw='True'

    By default Consult will return other information about the key, the raw
    option will return only the raw value.

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if recurse:
        query_params['recurse'] = True

    if raw:
        query_params['raw'] = True

    function = 'kv/{0}'.format(key)

    res = _query(
        function=function,
        query_params=query_params
    )

    if res['result'] and decode:
        for item in res['comment']:
            item['Value'] = base64.b64decode(item['Value'])

    if isinstance(res['comment'], list) and not recurse:
        ret['comment'] = res['comment'][0]
    else:
        ret['comment'] = res['comment']

    ret['result'] = res['result']

    return ret


def put(key, value, flags=None, cas=None, acquire=None, release=None):
    '''
    Put values into Consul

    :param key: The key to use as the starting point for the list.
    :param value: The value to set the key to.
    :param flags: This can be used to specify an unsigned value
                  between 0 and 2^64-1. Clients can choose to use
                  this however makes sense for their application.
    :param cas: This flag is used to turn the PUT into a
                Check-And-Set operation.
    :param acquire: This flag is used to turn the PUT into a
                    lock acquisition operation.
    :param release: This flag is used to turn the PUT into a
                    lock release operation.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.put key='web/key1' value="Hello there"

        salt '*' consul.put key='web/key1' value="Hello there"
                                acquire='d5d371f4-c380-5280-12fd-8810be175592'

        salt '*' consul.put key='web/key1' value="Hello there"
                                release='d5d371f4-c380-5280-12fd-8810be175592'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    current_key = get(key=key, recurse=False)

    if flags:
        if flags > 0 and flags < 2**64:
            query_params['flags'] = flags

    if isinstance(cas, int):
        if current_key['result']:
            if cas == 0:
                ret['comment'] = ('Key `{0}` exists, index must be '
                                  'non-zero.'.format(key))
                ret['result'] = False
                return ret

            if cas != current_key['comment']['ModifyIndex']:
                ret['comment'] = ('Key `{0}` exists, but index do '
                                  'not match.'.format(key))
                ret['result'] = False
                return ret

            query_params['cas'] = cas
        else:
            ret['comment'] = ('Key `{0}` does not exists, CAS argument '
                              'can not be used.'.format(key))
            ret['result'] = False
            return ret
    else:
        log.info('Key {0} does not exist. Skipping release.')

    if acquire:
        if acquire not in session_list(return_list=True):
            ret['comment'] = '`{0}` is not a valid session.'.format(acquire)
            ret['result'] = False
            return ret

        query_params['acquire'] = acquire

    if release:
        if current_key['result']:
            if 'Session' in current_key['result']:
                if current_key['result']['Session'] == release:
                    query_params['release'] = release
                else:
                    ret['comment'] = '`{0}` locked by another session.'.format(key)
                    ret['result'] = False
                    return ret
            else:
                ret['comment'] = '`{0}` is not a valid session.'.format(key)
                ret['result'] = False
        else:
            log.info('Key `{0}` does not exist. Skipping release.')

    function = 'kv/{0}'.format(key)

    res = _query(
        function=function,
        method='PUT',
        data=value,
        query_params=query_params
    )

    if res['result']:
        ret['comment'] = 'Added key `{0}` with value `{1}`.'.format(key, value)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to add key `{0}` with value `{1}`: `{2}`'.format(key, value, res['comment'])

    return ret


def delete(key, recurse=False, cas=None):
    '''
    Delete values from Consul

    :param key: The key to use as the starting point for the list.
    :param recurse: Delete values recursively beginning at the value of key.
    :param cas: This flag is used to turn the DELETE into
                a Check-And-Set operation.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.delete key='web'

        salt '*' consul.delete key='web' recurse='True'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if recurse:
        query_params['recurse'] = True

    if isinstance(cas, int):
        if cas > 0:
            query_params['cas'] = cas
        else:
            ret['comment'] = 'Check and Set Operation value must be greater than 0.'
            return ret

    function = 'kv/{0}'.format(key)

    res = _query(
        function=function,
        method='DELETE',
        query_params=query_params
    )

    if res['result']:
        ret['comment'] = 'Deleted `{0}` key.'.format(key)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to delete key `{0}`: `{1}`'.format(key, res['comment'])

    return ret


def agent_checks():
    '''
    Returns the checks the local agent is managing

    :return: Returns the checks the local agent is managing

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_checks

    '''
    return _query(function='agent/checks')


def agent_services():
    '''
    Returns the services the local agent is managing

    :return: Returns the services the local agent is managing

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_services

    '''
    return _query(function='agent/services')


def agent_members(wan=None):
    '''
    Returns the members as seen by the local serf agent

    :return: Returns the members as seen by the local serf agent

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_members

        salt '*' consul.agent_members wan=1

    '''
    query_params = {}

    if wan:
        query_params['wan'] = 1

    return _query(function='agent/members', query_params=query_params)


def agent_self():
    '''
    Returns the local node configuration

    :return: Returns the local node configuration

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_self

    '''
    return _query(function='agent/self')


def agent_maintenance(enable, reason=None):
    '''
    Manages node maintenance mode

    :param enable: The enable flag is required.
                   Acceptable values are either true
                   (to enter maintenance mode) or
                   false (to resume normal operation).
    :param reason: If provided, its value should be a
                   text string explaining the reason for
                   placing the node into maintenance mode.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_maintenance enable='False' reason='Upgrade in progress'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {'enable': False}

    if enable:
        query_params['enable'] = True

    if reason:
        query_params['reason'] = reason

    res = _query(
        function='agent/maintenance',
        method='PUT',
        query_params=query_params
    )

    if res['result']:
        ret['comment'] = 'Agent maintenance mode `{0}`.'.format('enabled' if enable else 'disabled')
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to change maintenance mode for agent: `{0}`'.format(res['comment'])

    return ret


def agent_join(address, wan=None):
    '''
    Triggers the local agent to join a node

    :param address: The address for the agent to connect to.
    :param wan: Causes the agent to attempt to join using the WAN pool.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_join address='192.168.1.1'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if wan:
        query_params['wan'] = wan

    function = 'agent/join/{0}'.format(address)

    res = _query(
        function=function,
        query_params=query_params
    )

    if res['result']:
        ret['comment'] = 'Node `{0}` joined.'.format(address)
        ret['result'] = True
    else:
        ret['comment'] = 'Node `{0}` was unable to join: `{1}`'.format(address, res['comment'])

    return ret


def agent_leave(node):
    '''
    Used to instruct the agent to force a node into the left state.

    :param node: The node the agent will force into left state
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_leave node='web1.example.com'

    '''
    ret = {'result': False, 'comment': ''}

    function = 'agent/force-leave/{0}'.format(node)

    res = _query(function=function)

    if res['result']:
        ret['comment'] = 'Node `{0}` put in leave state.'.format(node)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to change state for `{0}`: `{1}`'.format(node, res['comment'])

    return ret


def agent_check_register(name,
                         id_=None,
                         script=None,
                         http=None,
                         tcp=None,
                         ttl=None,
                         interval='5s',
                         notes=None):
    '''
    The register endpoint is used to add a new check to the local agent.

    :param name: The description of what the check is for.
    :param id_: The unique name to use for the check, if not
               provided 'name' is used.
    :param notes: Human readable description of the check.
    :param script: If script is provided, the check type is
                   a script, and Consul will evaluate that script
                   based on the interval parameter.
    :param http: Check will perform an HTTP GET request against
                 the value of HTTP (expected to be a URL) based
                 on the interval parameter.
    :param ttl: If a TTL type is used, then the TTL update endpoint
                must be used periodically to update the state of the check.
    :param interval: Interval at which the check should run.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_register name='Memory Utilization'
                script='/usr/local/bin/check_mem.py' interval='15s'

    '''
    ret = {'result': False, 'comment': ''}
    data = {'Name': name}

    check_count = [check for check in (script, http, tcp, ttl) if check]

    if len(check_count) > 1:
        raise SaltInvocationError('You can only select one check type')

    if notes:
        data['Notes'] = notes

    if id_:
        data['ID'] = id_

    if ttl:
        data['TTL'] = ttl

    if script:
        data['Script'] = script

    if http:
        data['HTTP'] = http

    if tcp:
        data['TCP'] = tcp

    data['Interval'] = interval

    res = _query(
        function='agent/check/register',
        method='PUT',
        data=data
    )

    if res['result']:
        ret['comment'] = 'Check `{0}` added to agent.'.format(name)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to add `{0}`check to agent: `{1}`'.format(name, res['comment'])

    return ret


def agent_check_deregister(check_id):
    '''
    The agent will take care of deregistering the check from the Catalog.

    :param check_id: The ID of the check to deregister from Consul.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_deregister check_id='Memory Utilization'

    '''
    ret = {'result': False, 'comment': ''}

    function = 'agent/check/deregister/{0}'.format(urlquote(check_id))

    res = _query(function=function)

    if res['result']:
        ret['comment'] = 'Check `{0}` removed from agent.'.format(check_id)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to remove `{0}` check from agent: `{1}`'.format(check_id, res['comment'])

    return ret


def agent_check_pass(check_id, note=None):
    '''
    This endpoint is used with a check that is of the TTL type. When this
    is called, the status of the check is set to passing and the TTL
    clock is reset.

    :param check_id: The ID of the check to mark as passing.
    :param note: A human-readable message with the status of the check.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_pass check_id='redis_check1' \
                note='Forcing check into passing state.'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if note:
        query_params['note'] = note

    function = 'agent/check/pass/{0}'.format(urlquote(check_id))

    res = _query(
        function=function,
        query_params=query_params,
    )

    if res['result']:
        ret['comment'] = 'Check `{0}` marked as passing.'.format(check_id)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to update check `{0}`: `{1}`'.format(check_id, res['comment'])

    return ret


def agent_check_warn(check_id, note=None):
    '''
    This endpoint is used with a check that is of the TTL type. When this
    is called, the status of the check is set to warning and the TTL
    clock is reset.

    :param check_id: The ID of the check to deregister from Consul.
    :param note: A human-readable message with the status of the check.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_warn check_id='redis_check1' \
                note='Forcing check into warning state.'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if note:
        query_params['note'] = note

    function = 'agent/check/warn/{0}'.format(urlquote(check_id))

    res = _query(
        function=function,
        query_params=query_params,
    )

    if res['result']:
        ret['comment'] = 'Check `{0}` marked as warning.'.format(check_id)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to update check `{0}`: `{1}`'.format(check_id, res['comment'])

    return ret


def agent_check_fail(check_id, note=None):
    '''
    This endpoint is used with a check that is of the TTL type. When this
    is called, the status of the check is set to critical and the
    TTL clock is reset.

    :param check_id: The ID of the check to deregister from Consul.
    :param note: A human-readable message with the status of the check.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_check_fail checkid='redis_check1' \
                note='Forcing check into critical state.'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if note:
        query_params['note'] = note

    function = 'agent/check/fail/{0}'.format(urlquote(check_id))

    res = _query(
        function=function,
        query_params=query_params,
    )

    if res['result']:
        ret['comment'] = 'Check `{0}` marked as critical.'.format(check_id)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to update check `{0}`: `{1}`'.format(check_id, res['comment'])

    return ret


def agent_service_register(name,
                           address=None,
                           port=None,
                           id_=None,
                           tags=None,
                           check_script=None,
                           check_http=None,
                           check_ttl=None,
                           interval='5s'):
    '''
    The used to add a new service, with an optional
    health check, to the local agent.

    :param name: A name describing the service.
    :param address: The address used by the service, defaults
                    to the address of the agent.
    :param port: The port used by the service.
    :param id_: Unique ID to identify the service, if not
               provided the value of the name parameter is used.
    :param tags: Identifying tags for service, string or list.
    :param check_script: If script is provided, the check type is
                   a script, and Consul will evaluate that script
                   based on the interval parameter.
    :param check_http: Check will perform an HTTP GET request against
                 the value of HTTP (expected to be a URL) based
                 on the interval parameter.
    :param check_ttl: If a TTL type is used, then the TTL update
                      endpoint must be used periodically to update
                      the state of the check.
    :param check_interval: Interval at which the check should run.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_service_register name='redis'
            tags='["master", "v1"]' address="127.0.0.1" port="8080"
            check_script="/usr/local/bin/check_redis.py" interval="10s"

    '''
    ret = {'result': False, 'comment': ''}
    data = {'Name': name}

    if address:
        data['Address'] = address

    if port:
        data['Port'] = port

    if id_:
        data['ID'] = id_

    if tags:
        if not isinstance(tags, list):
            tags = [tags]

        data['Tags'] = tags

    for check, check_name in [(check_script, 'Script'), (check_http, 'HTTP'), (check_ttl, 'TTL')]:
        if check:
            data['Check'] = {}

            data['Check'][check_name] = check
            data['Check']['Interval'] = interval

            break

    res = _query(
        function='agent/service/register',
        method='PUT',
        data=data
    )

    if res['result']:
        ret['comment'] = 'Service `{0}` registered on agent.'.format(name)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to register service `{0}`: `{1}`'.format(name, res['comment'])

    return ret


def agent_service_deregister(service_id):
    '''
    Used to remove a service.

    :param service_id: A serviceid describing the service.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_service_deregister service_id='redis'

    '''
    ret = {'result': False, 'comment': ''}

    function = 'agent/service/deregister/{0}'.format(service_id)

    res = _query(
        function=function,
        method='PUT',
    )

    if res['result']:
        ret['comment'] = 'Service `{0}` removed from agent.'.format(service_id)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to remove service `{0}`: `{1}`'.format(service_id, res['comment'])

    return ret


def agent_service_maintenance(service_id, enable=False, reason=None):
    '''
    Used to place a service into maintenance mode.

    :param service_id: A name of the service.
    :param enable: Whether the service should be enabled or disabled.
    :param reason: A human readable message of why the service was
                   enabled or disabled.
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.agent_service_maintenance service_id='redis'
                enable='True' reason='Down for upgrade'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {'enable': enable}

    if reason:
        query_params['reason'] = reason

    function = 'agent/service/maintenance/{0}'.format(service_id)

    res = _query(
        function=function,
        query_params=query_params
    )

    if res['result']:
        ret['comment'] = 'Service `{0}` set in maintenance mode.'.format(service_id)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to set service `{0}` to maintenance mode: `{1}`'.format(service_id, res['comment'])

    return ret


def session_create(name, lockdelay=None, node=None, checks=None, behavior=None, ttl=None):
    '''
    Used to create a session.

    :param lockdelay: Duration string using a "s" suffix for seconds.
                      The default is 15s.
    :param node: Must refer to a node that is already registered,
                 if specified. By default, the agent's own node
                 name is used.
    :param name: A human-readable name for the session
    :param checks: A list of associated health checks. It is highly
                   recommended that, if you override this list, you
                   include the default "serfHealth".
    :param behavior: Can be set to either release or delete. This controls
                     the behavior when a session is invalidated. By default,
                     this is release, causing any locks that are held to be
                     released. Changing this to delete causes any locks that
                     are held to be deleted. delete is useful for creating
                     ephemeral key/value entries.
    :param ttl: Session is invalidated if it is not renewed before
                the TTL expires
    :return: Boolean and message indicating success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_create node='node1' name='my-session'
                behavior='delete' ttl='3600s'

    '''
    ret = {'result': False, 'comment': ''}
    data = {'Name': name}

    for attr, val in [(lockdelay, 'LockDelay'), (node, 'Node'), (checks, 'Checks')]:
        if attr:
            data[val] = attr

    if behavior:
        if behavior not in ('delete', 'release'):
            ret['comment'] = 'Behavior must be either delete or release.'
            return ret

        data['Behavior'] = behavior

    if ttl:
        if str(ttl).endswith('s'):
            ttl = ttl[:-1]

        if int(ttl) < 0 or int(ttl) > 3600:
            ret['comment'] = 'TTL must be between 0 and 3600.'
            return ret

        data['TTL'] = '{0}s'.format(ttl)

    res = _query(
        function='session/create',
        method='PUT',
        data=data
    )

    if res['result']:
        ret['comment'] = 'Created session `{0}`'.format(name)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to create session `{0}`: `{1}`'.format(name, res['comment'])

    return ret


def session_list(datacenter=None, return_list=False):
    '''
    Used to list sessions.

    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param return_list: By default, all information about the sessions is
                        returned, using the return_list parameter will return
                        a list of session IDs.
    :return: A list of all available sessions.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_list

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    res = _query(
        function='session/list',
        query_params=query_params
    )

    if return_list:
        sessions = []
        for item in res['comment']:
            sessions.append(item['ID'])

        return sessions

    return res


def session_destroy(session, datacenter=None):
    '''
    Destroy session

    :param session: The ID of the session to destroy.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_destroy session='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    function = 'session/destroy/{0}'.format(session)

    res = _query(
        function=function,
        query_params=query_params
    )

    if res['result']:
        ret['comment'] = 'Session destroyed `{0}`'.format(session)
        ret['result'] = True
    else:
        ret['comment'] = 'Unable to destroy session `{0}`: `{1}`'.format(session, res['comment'])

    return ret


def session_info(session, datacenter=None):
    '''
    Information about a session

    :param session: The ID of the session to return information about.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.session_info session='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    function = 'session/info/{0}'.format(session)

    return _query(
        function=function,
        query_params=query_params
    )


def catalog_register(node,
                     address,
                     datacenter=None,
                     service=None,
                     service_address=None,
                     service_port=None,
                     service_id=None,
                     service_tags=None,
                     check=None,
                     check_service=None,
                     check_status=None,
                     check_id=None,
                     check_notes=None):
    '''
    Registers a new node, service, or check

    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param node: The node to register.
    :param address: The address of the node.
    :param service: The service that will be registered.
    :param service_address: The address that the service listens on.
    :param service_port: The port for the service.
    :param service_id: A unique identifier for the service, if this is not
                       provided "name" will be used.
    :param service_tags: Any tags associated with the service.
    :param check: The name of the health check to register
    :param check_status: The initial status of the check,
                         must be one of unknown, passing, warning, or critical.
    :param check_service: The service that the check is performed against.
    :param check_id: Unique identifier for the service.
    :param check_notes: An opaque field that is meant to hold human-readable text.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_register node='node1' address='192.168.1.1'
            service='redis' service_address='127.0.0.1' service_port='8080'
            service_id='redis_server1'

    '''
    ret = {'result': False, 'comment': ''}
    data = {'Node': node, 'Address': address}

    if datacenter:
        data['Datacenter'] = datacenter

    if service:
        data['Service'] = {}
        data['Service']['Service'] = service

        for param, param_name in [(service_address, 'Address'), (service_port, 'Port'), (service_id, 'ID')]:
            if param:
                data['Service'][param_name] = param

        if service_tags:
            tags = service_tags
            if not isinstance(tags, list):
                tags = [tags]

            data['Service']['Tags'] = tags

    if check:
        data['Check'] = {}
        data['Check']['Name'] = check

        for param, param_name in [(check_service, 'ServiceID'), (check_id, 'CheckID'), (check_notes, 'Notes')]:
            if param:
                data['Check'][param_name] = param

        if check_status:
            if check_status not in ('unknown', 'passing', 'warning', 'critical'):
                raise SaltInvocationError('Check status must be unknown, passing, warning, or critical.')

            data['Check']['Status'] = check_status

    res = _query(
        function='catalog/register',
        method='PUT',
        data=data
    )

    if res['result']:
        ret['comment'] = 'Catalog registration for `{0}` successful'.format(node)
        ret['result'] = True
    else:
        ret['comment'] = ('Catalog registration for `{0}` failed: '
                          '`{1}`'.format(node, res['comment']))

    return ret


def catalog_deregister(node, datacenter=None, check_id=None, service_id=None):
    '''
    Deregisters a node, service, or check

    :param node: The node to deregister.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param check_id: The ID of the health check to deregister.
    :param service_id: The ID of the service to deregister.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_deregister node='node1'
            service_id='redis_server1' check_id='redis_check1'

    '''
    ret = {'result': False, 'comment': ''}
    data = {'Node': node}

    for param, param_name in [(datacenter, 'Datacenter'), (check_id, 'CheckID'), (service_id, 'ServiceID')]:
        if param:
            data[param_name] = param

    res = _query(
        function='catalog/deregister',
        method='PUT',
        data=data
    )

    if res['result']:
        ret['comment'] = 'Catalog item `{0}` removed.'.format(node)
        ret['result'] = True
    else:
        ret['comment'] = ('Removing Catalog item `{0}` failed: '
                          '`{1}`'.format(node, res['comment']))

    return ret


def catalog_datacenters():
    '''
    Return list of available datacenters from catalog.

    :return: The list of available datacenters.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_datacenters

    '''
    return _query(function='catalog/datacenters')


def catalog_nodes(datacenter=None):
    '''
    Return list of available nodes from catalog.

    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: The list of available nodes.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_nodes

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    return _query(
        function='catalog/nodes',
        query_params=query_params
    )


def catalog_services(datacenter=None):
    '''
    Return list of available services rom catalog.

    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: The list of available services.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_services

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    return _query(
        function='catalog/services',
        query_params=query_params
    )


def catalog_service(service, datacenter=None, tag=None):
    '''
    Information about the registered service.

    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param tag: Filter returned services with tag parameter.
    :return: Information about the requested service.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_service service='redis'

    '''
    query_params = {}

    for param, name in [(datacenter, 'dc'), (tag, 'tag')]:
        if param:
            query_params[name] = param

    function = 'catalog/service/{0}'.format(service)

    return _query(
        function=function,
        query_params=query_params
    )


def catalog_node(node, datacenter=None):
    '''
    Information about the registered node.

    :param node: The node to request information about.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.catalog_node node='node1'

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    function = 'catalog/node/{0}'.format(node)

    return _query(
        function=function,
        query_params=query_params
    )


def health_node(node, datacenter=None):
    '''
    Health information about the registered node.

    :param node: The node to request health information about.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Health information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_node node='node1'

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    function = 'health/node/{0}'.format(node)

    return _query(
        function=function,
        query_params=query_params
    )


def health_checks(service, datacenter=None):
    '''
    Health information about the registered service.

    :param service: The service to request health information about.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: Health information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_checks service='redis1'

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    function = 'health/checks/{0}'.format(service)

    return _query(
        function=function,
        query_params=query_params
    )


def health_service(service, datacenter=None, tag=None, passing=None):
    '''
    Health information about the registered service.

    :param service: The service to request health information about.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :param tag: Filter returned services with tag parameter.
    :param passing: Filter results to only nodes with all
                    checks in the passing state.
    :return: Health information about the requested node.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_service service='redis1'

        salt '*' consul.health_service service='redis1' passing='True'

    '''
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    if tag:
        query_params['tag'] = tag

    if passing:
        query_params['passing'] = passing

    function = 'health/service/{0}'.format(service)

    return _query(
        function=function,
        query_params=query_params
    )


def health_state(state, datacenter=None):
    '''
    Returns the checks in the state provided on the path.

    :param state: The state to show checks for. The supported states
                  are any, unknown, passing, warning, or critical.
                  The any state is a wildcard that can be used to
                  return all checks.
    :param datacenter: By default, the datacenter of the agent is queried;
               however, the dc can be provided using the "dc" parameter.
    :return: The checks in the provided state.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.health_state state='redis1'

        salt '*' consul.health_state service='redis1' passing='True'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    if state not in ('any', 'unknown', 'passing', 'warning', 'critical'):
        ret['comment'] = ('State must be any, unknown, passing, '
                          'warning, or critical.')
        return ret

    function = 'health/state/{0}'.format(state)

    return _query(
        function=function,
        query_params=query_params
    )


def status_leader():
    '''
    Returns the current Raft leader

    :return: The address of the Raft leader.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.status_leader

    '''
    return _query(function='status/leader')


def status_peers():
    '''
    Returns the current Raft peer set

    :return: Retrieves the Raft peers for the
             datacenter in which the the agent is running.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.status_peers

    '''
    return _query(function='status/peers')


def acl_create(name, type_=None, rules=None):
    '''
    Create a new ACL token.

    :param name: Meaningful indicator of the ACL's purpose.
    :param type: Type is either client or management. A management
                 token is comparable to a root user and has the
                 ability to perform any action including creating,
                 modifying, and deleting ACLs.
    :param rules: The Consul server URL.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_create my-app-token client

        salt '*' consul.acl_create my-app-token type_=client

    '''
    ret = {'result': False, 'comment': ''}
    data = {'Type': type_, 'Rules': rules, 'Name': name}

    if type_ and type_ not in ('client', 'management'):
        raise SaltInvocationError('Invalid type.')

    data = dict((i, j) for i, j in data.iteritems() if j)

    res = _query(
        data=data,
        method='PUT',
        function='acl/create'
    )

    if res['result']:
        ret['comment'] = 'ACL `{0}` created.'.format(name)
        ret['result'] = True
    else:
        ret['comment'] = ('Unable to create `{0}` ACL token: '
                          '`{1}`'.format(name, res['comment']))

    return ret


def acl_update(name, id_, type_=None, rules=None):
    '''
    Update an ACL token.

    :param name: Meaningful indicator of the ACL's purpose.
    :param id_: Unique identifier for the ACL to update.
    :param type: Type is either client or management. A management
                 token is comparable to a root user and has the
                 ability to perform any action including creating,
                 modifying, and deleting ACLs.
    :param rules: The Consul server URL.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_update my-new-token-name \
            20940f05-56c7-90f9-c9b2-fe7ee388d1e2

        salt '*' consul.acl_update my-new-token-name \
            id_=20940f05-56c7-90f9-c9b2-fe7ee388d1e2

    '''
    ret = {'result': False, 'comment': ''}
    data = data = {
        'Type': type_,
        'Rules': rules,
        'Name': name,
        'ID': id_
    }

    if type_ and type_ not in ('client', 'management'):
        raise SaltInvocationError('Invalid type.')

    data = dict((i, j) for i, j in data.iteritems() if j)

    res = _query(
        data=data,
        method='PUT',
        function='acl/update'
    )

    if res['result']:
        ret['comment'] = 'ACL `{0}` updated.'.format(id_)
        ret['result'] = True
    else:
        ret['comment'] = ('Updating ACL `{0}` failed: '
                          '`{1}`'.format(id_, res['comment']))

    return ret


def acl_delete(id_):
    '''
    Delete an ACL token.

    :param id_: Unique identifier for the ACL to update.
    :return: Boolean & message of success or failure.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_delete c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716

        salt '*' consul.acl_delete id_='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    '''
    ret = {'result': False, 'comment': ''}

    function = 'acl/destroy/{0}'.format(id_)

    res = _query(
        method='PUT',
        function=function
    )

    if res['result']:
        ret['comment'] = 'ACL `{0}` deleted.'.format(id_)
        ret['result'] = True
    else:
        ret['comment'] = ('Removing ACL `{0}` failed: '
                          '`{1}`'.format(id_, res['comment']))

    return ret


def acl_info(id_):
    '''
    Information about an ACL token.

    :param id_: Unique identifier for the ACL to update.
    :return: Information about the ACL requested.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_info id_='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    '''
    function = 'acl/info/{0}'.format(id_)

    return _query(function=function)


def acl_clone(id_):
    '''
    Creates a new token by cloning an existing token.

    :param id_: Unique identifier for the ACL to update.
    :return: Boolean, message of success or
             failure, and new ID of cloned ACL.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_clone c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716

        salt '*' consul.acl_clone id_='c1c4d223-91cb-3d1f-1ee8-f2af9e7b6716'

    '''
    ret = {'result': False, 'comment': ''}

    function = 'acl/clone/{0}'.format(id_)

    res = _query(
        method='PUT',
        function=function
    )

    if res['result']:
        ret['comment'] = 'ACL `{0}` cloned.'.format(id_)
        ret['result'] = True
    else:
        ret['comment'] = ('Cloning ACL `{0}` failed: '
                          '`{1}`'.format(id_, res['comment']))

    return ret


def acl_list():
    '''
    List the ACL tokens.

    :return: List of ACLs

    CLI Example:

    .. code-block:: bash

        salt '*' consul.acl_list

    '''
    return _query(function='acl/list')


def event_fire(name, datacenter=None, node=None, service=None, tag=None):
    '''
     Trigger a new user event

    :param name: The name of the event to fire.
    :param datacenter: Specify another datacenter
    :param node: Filter by node name.
    :param service: Filter by service name.
    :param tag: Filter by tag name.
    :return: ID field uniquely identifies the newly fired event.

    CLI Example:

    .. code-block:: bash

        salt '*' consul.event_fire name='deploy'

    '''
    ret = {'result': False, 'comment': ''}
    query_params = {}

    if datacenter:
        query_params['dc'] = datacenter

    if node:
        query_params['node'] = node

    if service:
        query_params['service'] = service

    if tag:
        query_params['tag'] = tag

    function = 'event/fire/{0}'.format(name)

    res = _query(
        query_params=query_params,
        method='PUT',
        function=function
    )

    if res['result']:
        ret['comment'] = 'Event `{0}` fired.'.format(name)
        ret['result'] = True
    else:
        ret['comment'] = ('Event `{0}` failed to '
                          'fire: `{1}`'.format(name, res['comment']))

    return ret


def event_list(name=None, service=None, tag=None):
    '''
    List most recent events.

    :param name: The name of the event to fire.
    :return: List recent events

    CLI Example:

    .. code-block:: bash

        salt '*' consul.event_list

    '''
    query_params = {}

    if name:
        query_params['name'] = name

    if service:
        query_params['service'] = service

    if tag:
        query_params['tag'] = tag

    return _query(
        query_params=query_params,
        function='event/list'
    )
