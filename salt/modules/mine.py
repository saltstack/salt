# -*- coding: utf-8 -*-
'''
The function cache system allows for data to be stored on the master so it can be easily read by other minions
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import copy
import logging
import time
import traceback

# Import salt libs
import salt.crypt
import salt.payload
import salt.utils.args
import salt.utils.event
import salt.utils.network
import salt.utils.versions
from salt.exceptions import SaltClientError

# Import 3rd-party libs
from salt.ext import six

MINE_INTERNAL_KEYWORDS = frozenset([
    '__pub_user',
    '__pub_arg',
    '__pub_fun',
    '__pub_jid',
    '__pub_tgt',
    '__pub_tgt_type',
    '__pub_ret'
])

__proxyenabled__ = ['*']

log = logging.getLogger(__name__)


def _auth():
    '''
    Return the auth object
    '''
    if 'auth' not in __context__:
        try:
            __context__['auth'] = salt.crypt.SAuth(__opts__)
        except SaltClientError:
            log.error('Could not authenticate with master.'
                      'Mine data will not be transmitted.')
    return __context__['auth']


def _mine_function_available(func):
    if func not in __salt__:
        log.error('Function %s in mine_functions not available', func)
        return False
    return True


def _mine_send(load, opts):
    eventer = salt.utils.event.MinionEvent(opts, listen=False)
    event_ret = eventer.fire_event(load, '_minion_mine')
    # We need to pause here to allow for the decoupled nature of
    # events time to allow the mine to propagate
    time.sleep(0.5)
    return event_ret


def _mine_get(load, opts):
    if opts.get('transport', '') in ('zeromq', 'tcp'):
        try:
            load['tok'] = _auth().gen_token(b'salt')
        except AttributeError:
            log.error('Mine could not authenticate with master. '
                      'Mine could not be retrieved.'
                      )
            return False
    channel = salt.transport.Channel.factory(opts)
    ret = channel.send(load)
    return ret


def update(clear=False, mine_functions=None):
    '''
    Execute the configured functions and send the data back up to the master.
    The functions to be executed are merged from the master config, pillar and
    minion config under the option `mine_functions`:

    .. code-block:: yaml

        mine_functions:
          network.ip_addrs:
            - eth0
          disk.usage: []

    This function accepts the following arguments:

    clear: False
        Boolean flag specifying whether updating will clear the existing
        mines, or will update. Default: `False` (update).

    mine_functions
        Update the mine data on certain functions only.
        This feature can be used when updating the mine for functions
        that require refresh at different intervals than the rest of
        the functions specified under `mine_functions` in the
        minion/master config or pillar.
        A potential use would be together with the `scheduler`, for example:

        .. code-block:: yaml

            schedule:
              lldp_mine_update:
                function: mine.update
                kwargs:
                    mine_functions:
                      net.lldp: []
                hours: 12

        In the example above, the mine for `net.lldp` would be refreshed
        every 12 hours, while  `network.ip_addrs` would continue to be updated
        as specified in `mine_interval`.

    The function cache will be populated with information from executing these
    functions

    CLI Example:

    .. code-block:: bash

        salt '*' mine.update
    '''
    m_data = {}
    if not mine_functions:
        m_data = __salt__['config.merge']('mine_functions', {})
        # If we don't have any mine functions configured, then we should just bail out
        if not m_data:
            return
    elif mine_functions and isinstance(mine_functions, list):
        m_data = dict((fun, {}) for fun in mine_functions)
    elif mine_functions and isinstance(mine_functions, dict):
        m_data = mine_functions
    else:
        return

    data = {}
    for func in m_data:
        try:
            if m_data[func] and isinstance(m_data[func], dict):
                mine_func = m_data[func].pop('mine_function', func)
                if not _mine_function_available(mine_func):
                    continue
                data[func] = __salt__[mine_func](**m_data[func])
            elif m_data[func] and isinstance(m_data[func], list):
                mine_func = func
                if isinstance(m_data[func][0], dict) and 'mine_function' in m_data[func][0]:
                    mine_func = m_data[func][0]['mine_function']
                    m_data[func].pop(0)

                if not _mine_function_available(mine_func):
                    continue
                data[func] = __salt__[mine_func](*m_data[func])
            else:
                if not _mine_function_available(func):
                    continue
                data[func] = __salt__[func]()
        except Exception:
            trace = traceback.format_exc()
            log.error('Function %s in mine_functions failed to execute', func)
            log.debug('Error: %s', trace)
            continue
    if __opts__['file_client'] == 'local':
        if not clear:
            old = __salt__['data.get']('mine_cache')
            if isinstance(old, dict):
                old.update(data)
                data = old
        return __salt__['data.update']('mine_cache', data)
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id'],
            'clear': clear,
    }
    return _mine_send(load, __opts__)


def send(func, *args, **kwargs):
    '''
    Send a specific function to the mine.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.send network.ip_addrs eth0
        salt '*' mine.send eth0_ip_addrs mine_function=network.ip_addrs eth0
    '''
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    mine_func = kwargs.pop('mine_function', func)
    if mine_func not in __salt__:
        return False
    data = {}
    arg_data = salt.utils.args.arg_lookup(__salt__[mine_func])
    func_data = copy.deepcopy(kwargs)
    for ind, _ in enumerate(arg_data.get('args', [])):
        try:
            func_data[arg_data['args'][ind]] = args[ind]
        except IndexError:
            # Safe error, arg may be in kwargs
            pass
    f_call = salt.utils.args.format_call(
        __salt__[mine_func],
        func_data,
        expected_extra_kws=MINE_INTERNAL_KEYWORDS)
    for arg in args:
        if arg not in f_call['args']:
            f_call['args'].append(arg)
    try:
        if 'kwargs' in f_call:
            data[func] = __salt__[mine_func](*f_call['args'], **f_call['kwargs'])
        else:
            data[func] = __salt__[mine_func](*f_call['args'])
    except Exception as exc:
        log.error('Function %s in mine.send failed to execute: %s',
                  mine_func, exc)
        return False
    if __opts__['file_client'] == 'local':
        old = __salt__['data.get']('mine_cache')
        if isinstance(old, dict):
            old.update(data)
            data = old
        return __salt__['data.update']('mine_cache', data)
    load = {
            'cmd': '_mine',
            'data': data,
            'id': __opts__['id'],
    }
    return _mine_send(load, __opts__)


def get(tgt,
        fun,
        tgt_type='glob',
        exclude_minion=False,
        expr_form=None):
    '''
    Get data from the mine based on the target, function and tgt_type

    Targets can be matched based on any standard matching system that can be
    matched on the master via these keywords:

    - glob
    - pcre
    - grain
    - grain_pcre
    - compound
    - pillar
    - pillar_pcre

    Note that all pillar matches, whether using the compound matching system or
    the pillar matching system, will be exact matches, with globbing disabled.

    exclude_minion
        Excludes the current minion from the result set

    CLI Example:

    .. code-block:: bash

        salt '*' mine.get '*' network.interfaces
        salt '*' mine.get 'os:Fedora' network.interfaces grain
        salt '*' mine.get 'G@os:Fedora and S@192.168.5.0/24' network.ipaddrs compound

    .. seealso:: Retrieving Mine data from Pillar and Orchestrate

        This execution module is intended to be executed on minions.
        Master-side operations such as Pillar or Orchestrate that require Mine
        data should use the :py:mod:`Mine Runner module <salt.runners.mine>`
        instead; it can be invoked from a Pillar SLS file using the
        :py:func:`saltutil.runner <salt.modules.saltutil.runner>` module. For
        example:

        .. code-block:: jinja

            {% set minion_ips = salt.saltutil.runner('mine.get',
                tgt='*',
                fun='network.ip_addrs',
                tgt_type='glob') %}
    '''
    # remember to remove the expr_form argument from this function when
    # performing the cleanup on this deprecation.
    if expr_form is not None:
        salt.utils.versions.warn_until(
            'Fluorine',
            'the target type should be passed using the \'tgt_type\' '
            'argument instead of \'expr_form\'. Support for using '
            '\'expr_form\' will be removed in Salt Fluorine.'
        )
        tgt_type = expr_form

    if __opts__['file_client'] == 'local':
        ret = {}
        is_target = {'glob': __salt__['match.glob'],
                     'pcre': __salt__['match.pcre'],
                     'list': __salt__['match.list'],
                     'grain': __salt__['match.grain'],
                     'grain_pcre': __salt__['match.grain_pcre'],
                     'ipcidr': __salt__['match.ipcidr'],
                     'compound': __salt__['match.compound'],
                     'pillar': __salt__['match.pillar'],
                     'pillar_pcre': __salt__['match.pillar_pcre'],
                     }[tgt_type](tgt)
        if is_target:
            data = __salt__['data.get']('mine_cache')
            if isinstance(data, dict) and fun in data:
                ret[__opts__['id']] = data[fun]
        return ret
    load = {
            'cmd': '_mine_get',
            'id': __opts__['id'],
            'tgt': tgt,
            'fun': fun,
            'tgt_type': tgt_type,
    }
    ret = _mine_get(load, __opts__)
    if exclude_minion:
        if __opts__['id'] in ret:
            del ret[__opts__['id']]
    return ret


def delete(fun):
    '''
    Remove specific function contents of minion. Returns True on success.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.delete 'network.interfaces'
    '''
    if __opts__['file_client'] == 'local':
        data = __salt__['data.get']('mine_cache')
        if isinstance(data, dict) and fun in data:
            del data[fun]
        return __salt__['data.update']('mine_cache', data)
    load = {
            'cmd': '_mine_delete',
            'id': __opts__['id'],
            'fun': fun,
    }
    return _mine_send(load, __opts__)


def flush():
    '''
    Remove all mine contents of minion. Returns True on success.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.flush
    '''
    if __opts__['file_client'] == 'local':
        return __salt__['data.update']('mine_cache', {})
    load = {
            'cmd': '_mine_flush',
            'id': __opts__['id'],
    }
    return _mine_send(load, __opts__)


def get_docker(interfaces=None, cidrs=None, with_container_id=False):
    '''
    Get all mine data for 'docker.get_containers' and run an aggregation
    routine. The "interfaces" parameter allows for specifying which network
    interfaces to select ip addresses from. The "cidrs" parameter allows for
    specifying a list of cidrs which the ip address must match.

    with_container_id
        Boolean, to expose container_id in the list of results

        .. versionadded:: 2015.8.2


    CLI Example:

    .. code-block:: bash

        salt '*' mine.get_docker
        salt '*' mine.get_docker interfaces='eth0'
        salt '*' mine.get_docker interfaces='["eth0", "eth1"]'
        salt '*' mine.get_docker cidrs='107.170.147.0/24'
        salt '*' mine.get_docker cidrs='["107.170.147.0/24", "172.17.42.0/24"]'
        salt '*' mine.get_docker interfaces='["eth0", "eth1"]' cidrs='["107.170.147.0/24", "172.17.42.0/24"]'
    '''
    # Enforce that interface and cidr are lists
    if interfaces:
        interface_ = []
        interface_.extend(interfaces if isinstance(interfaces, list) else [interfaces])
        interfaces = interface_
    if cidrs:
        cidr_ = []
        cidr_.extend(cidrs if isinstance(cidrs, list) else [cidrs])
        cidrs = cidr_

    # Get docker info
    cmd = 'docker.ps'
    docker_hosts = get('*', cmd)

    proxy_lists = {}

    # Process docker info
    for containers in six.itervalues(docker_hosts):
        host = containers.pop('host')
        host_ips = []

        # Prepare host_ips list
        if not interfaces:
            for info in six.itervalues(host['interfaces']):
                if 'inet' in info:
                    for ip_ in info['inet']:
                        host_ips.append(ip_['address'])
        else:
            for interface in interfaces:
                if interface in host['interfaces']:
                    if 'inet' in host['interfaces'][interface]:
                        for item in host['interfaces'][interface]['inet']:
                            host_ips.append(item['address'])
        host_ips = list(set(host_ips))

        # Filter out ips from host_ips with cidrs
        if cidrs:
            good_ips = []
            for cidr in cidrs:
                for ip_ in host_ips:
                    if salt.utils.network.in_subnet(cidr, [ip_]):
                        good_ips.append(ip_)
            host_ips = list(set(good_ips))

        # Process each container
        for container in six.itervalues(containers):
            container_id = container['Info']['Id']
            if container['Image'] not in proxy_lists:
                proxy_lists[container['Image']] = {}
            for dock_port in container['Ports']:
                # IP exists only if port is exposed
                ip_address = dock_port.get('IP')
                # If port is 0.0.0.0, then we must get the docker host IP
                if ip_address == '0.0.0.0':
                    for ip_ in host_ips:
                        containers = proxy_lists[container['Image']].setdefault('ipv4', {}).setdefault(dock_port['PrivatePort'], [])
                        container_network_footprint = '{0}:{1}'.format(ip_, dock_port['PublicPort'])
                        if with_container_id:
                            value = (container_network_footprint, container_id)
                        else:
                            value = container_network_footprint
                        if value not in containers:
                            containers.append(value)
                elif ip_address:
                    containers = proxy_lists[container['Image']].setdefault('ipv4', {}).setdefault(dock_port['PrivatePort'], [])
                    container_network_footprint = '{0}:{1}'.format(dock_port['IP'], dock_port['PublicPort'])
                    if with_container_id:
                        value = (container_network_footprint, container_id)
                    else:
                        value = container_network_footprint
                    if value not in containers:
                        containers.append(value)

    return proxy_lists


def valid():
    '''
    List valid entries in mine configuration.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.valid
    '''
    m_data = __salt__['config.merge']('mine_functions', {})
    # If we don't have any mine functions configured, then we should just bail out
    if not m_data:
        return

    data = {}
    for func in m_data:
        if m_data[func] and isinstance(m_data[func], dict):
            mine_func = m_data[func].pop('mine_function', func)
            if not _mine_function_available(mine_func):
                continue
            data[func] = {mine_func: m_data[func]}
        elif m_data[func] and isinstance(m_data[func], list):
            mine_func = func
            if isinstance(m_data[func][0], dict) and 'mine_function' in m_data[func][0]:
                mine_func = m_data[func][0]['mine_function']
                m_data[func].pop(0)

            if not _mine_function_available(mine_func):
                continue
            data[func] = {mine_func: m_data[func]}
        else:
            if not _mine_function_available(func):
                continue
            data[func] = m_data[func]

    return data
