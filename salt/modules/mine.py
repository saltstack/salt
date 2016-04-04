# -*- coding: utf-8 -*-
'''
The function cache system allows for data to be stored on the master so it can be easily read by other minions
'''

# Import python libs
from __future__ import absolute_import
import copy
import logging
import time
import traceback

# Import salt libs
import salt.crypt
import salt.payload
import salt.utils
import salt.utils.network
import salt.utils.event
from salt.exceptions import SaltClientError

# Import 3rd-party libs
import salt.ext.six as six

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
        log.error('Function {0} in mine_functions not available'
                 .format(func))
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
            load['tok'] = _auth().gen_token('salt')
        except AttributeError:
            log.error('Mine could not authenticate with master. '
                      'Mine could not be retrieved.'
                      )
            return False
    channel = salt.transport.Channel.factory(opts)
    ret = channel.send(load)
    return ret


def update(clear=False):
    '''
    Execute the configured functions and send the data back up to the master
    The functions to be executed are merged from the master config, pillar and
    minion config under the option "function_cache":

    .. code-block:: yaml

        mine_functions:
          network.ip_addrs:
            - eth0
          disk.usage: []

    The function cache will be populated with information from executing these
    functions

    CLI Example:

    .. code-block:: bash

        salt '*' mine.update
    '''
    m_data = __salt__['config.merge']('mine_functions', {})
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
            log.error('Function {0} in mine_functions failed to execute'
                      .format(func))
            log.debug('Error: {0}'.format(trace))
            continue
    if __opts__['file_client'] == 'local':
        if not clear:
            old = __salt__['data.getval']('mine_cache')
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
    kwargs = salt.utils.clean_kwargs(**kwargs)
    mine_func = kwargs.pop('mine_function', func)
    if mine_func not in __salt__:
        return False
    data = {}
    arg_data = salt.utils.arg_lookup(__salt__[mine_func])
    func_data = copy.deepcopy(kwargs)
    for ind, _ in enumerate(arg_data.get('args', [])):
        try:
            func_data[arg_data['args'][ind]] = args[ind]
        except IndexError:
            # Safe error, arg may be in kwargs
            pass
    f_call = salt.utils.format_call(__salt__[mine_func],
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
        log.error('Function {0} in mine.send failed to execute: {1}'
                  .format(mine_func, exc))
        return False
    if __opts__['file_client'] == 'local':
        old = __salt__['data.getval']('mine_cache')
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


def get(tgt, fun, expr_form='glob'):
    '''
    Get data from the mine based on the target, function and expr_form

    Targets can be matched based on any standard matching system that can be
    matched on the master via these keywords::

        glob
        pcre
        grain
        grain_pcre
        compound
        pillar
        pillar_pcre

    Note that all pillar matches, whether using the compound matching system or
    the pillar matching system, will be exact matches, with globbing disabled.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.get '*' network.interfaces
        salt '*' mine.get 'os:Fedora' network.interfaces grain
        salt '*' mine.get 'os:Fedora and S@192.168.5.0/24' network.ipaddrs compound
    '''
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
                     }[expr_form](tgt)
        if is_target:
            data = __salt__['data.getval']('mine_cache')
            if isinstance(data, dict) and fun in data:
                ret[__opts__['id']] = data[fun]
        return ret
    load = {
            'cmd': '_mine_get',
            'id': __opts__['id'],
            'tgt': tgt,
            'fun': fun,
            'expr_form': expr_form,
    }
    return _mine_get(load, __opts__)


def delete(fun):
    '''
    Remove specific function contents of minion. Returns True on success.

    CLI Example:

    .. code-block:: bash

        salt '*' mine.delete 'network.interfaces'
    '''
    if __opts__['file_client'] == 'local':
        data = __salt__['data.getval']('mine_cache')
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
    cmd = 'dockerng.ps'
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
