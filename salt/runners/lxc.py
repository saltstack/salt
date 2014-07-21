# -*- coding: utf-8 -*-
'''
Control Linux Containers via Salt

:depends: lxc execution module
'''

# Import python libs
from __future__ import print_function
import time
import os
import copy
import logging

# Import Salt libs
from salt.utils.odict import OrderedDict
import salt.client
import salt.output
import salt.utils.virt
import salt.utils.cloud
import salt.key


log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}


def _do(name, fun):
    '''
    Invoke a function in the lxc module with no args
    '''
    host = find_guest(name, quiet=True)
    if not host:
        return False

    client = salt.client.get_local_client(__opts__['conf_file'])
    cmd_ret = client.cmd_iter(
            host,
            'lxc.{0}'.format(fun),
            [name],
            timeout=60)
    data = next(cmd_ret)
    data = data.get(host, {}).get('ret', None)
    if data:
        data = {host: data}
    return data


def _do_names(names, fun):
    '''
    Invoke a function in the lxc module with no args
    '''
    ret = {}
    hosts = find_guests(names)
    if not hosts:
        return False

    client = salt.client.get_local_client(__opts__['conf_file'])
    cmds = []
    for host, sub_names in hosts.items():
        for name in sub_names:
            cmds.append(client.cmd_iter(
                    host,
                    'lxc.{0}'.format(fun),
                    [name],
                    timeout=60))
    for cmd in cmds:
        data = next(cmd)
        data = data.get(host, {}).get('ret', None)
        if data:
            ret.update({host: data})
    return ret


def find_guest(name, quiet=False):
    '''
    Returns the host for a container.

    .. code-block:: bash

        salt-run lxc.find_guest name
    '''
    for data in _list_iter():
        host, l = data.items()[0]
        for x in 'running', 'frozen', 'stopped':
            if name in l[x]:
                if not quiet:
                    salt.output.display_output(
                            host,
                            'lxc_find_host',
                            __opts__)
                return host
    return None


def find_guests(names):
    '''
    Return a dict of hosts and named guests
    '''
    ret = {}
    names = names.split(',')
    for data in _list_iter():
        host, stat = data.items()[0]
        for state in stat:
            for name in stat[state]:
                if name in names:
                    if host in ret:
                        ret[host].append(name)
                    else:
                        ret[host] = [name]
    return ret


def init(names, host=None, saltcloud_mode=False, quiet=False, **kwargs):
    '''
    Initialize a new container


    .. code-block:: bash

        salt-run lxc.init name host=minion_id [cpuset=cgroups_cpuset] \\
                [cpushare=cgroups_cpushare] [memory=cgroups_memory] \\
                [template=lxc template name] [clone=original name] \\
                [nic=nic_profile] [profile=lxc_profile] \\
                [nic_opts=nic_opts] [start=(true|false)] \\
                [seed=(true|false)] [install=(true|false)] \\
                [config=minion_config] [snapshot=(true|false)]

    names
        Name of the containers, supports a single name or a comma delimited
        list of names.

    host
        Minion to start the container on. Required.

    saltcloud_mode
        init the container with the saltcloud opts format instead
        See lxc.init_interface module documentation

    cpuset
        cgroups cpuset.

    cpushare
        cgroups cpu shares.

    memory
        cgroups memory limit, in MB.

    template
        Name of LXC template on which to base this container

    clone
        Clone this container from an existing container

    nic
        Network interfaces profile (defined in config or pillar).

    profile
        A LXC profile (defined in config or pillar).

    nic_opts
        Extra options for network interfaces. E.g:

        ``{"eth0": {"mac": "aa:bb:cc:dd:ee:ff", "ipv4": "10.1.1.1", "ipv6": "2001:db8::ff00:42:8329"}}``

    start
        Start the newly created container.

    seed
        Seed the container with the minion config and autosign its key.
        Default: true

    install
        If salt-minion is not already installed, install it. Default: true

    config
        Optional config parameters. By default, the id is set to
        the name of the container.
    '''
    ret = {'comment': '', 'result': True}
    if host is None:
        # TODO: Support selection of host based on available memory/cpu/etc.
        ret['comment'] = 'A host must be provided'
        ret['result'] = False
        return ret
    if isinstance(names, basestring):
        names = names.split(',')
    if not isinstance(names, list):
        ret['comment'] = 'Container names are not formed as a list'
        ret['result'] = False
        return ret
    log.info('Searching for LXC Hosts')
    data = __salt__['lxc.list'](host, quiet=True)
    for host, containers in data.items():
        for name in names:
            if name in sum(containers.values(), []):
                log.info('Container \'{0}\' already exists'
                         ' on host \'{1}\','
                         ' init can be a NO-OP'.format(
                             name, host))
    if host not in data:
        ret['comment'] = 'Host \'{0}\' was not found'.format(host)
        ret['result'] = False
        return ret

    client = salt.client.get_local_client(__opts__['conf_file'])

    kw = dict((k, v) for k, v in kwargs.items() if not k.startswith('__'))
    pub_key = kw.get('pub_key', None)
    priv_key = kw.get('priv_key', None)
    explicit_auth = pub_key and priv_key
    approve_key = kw.get('approve_key', True)
    seeds = {}
    if approve_key and not explicit_auth:
        skey = salt.key.Key(__opts__)
        all_minions = skey.all_keys().get('minions', [])
        for name in names:
            seed = kwargs.get('seed', True)
            if name in all_minions:
                try:
                    if client.cmd(name, 'test.ping', timeout=20).get(name, None):
                        seed = False
                except (TypeError, KeyError):
                    pass
            seeds[name] = seed
            kv = salt.utils.virt.VirtKey(host, name, __opts__)
            if kv.authorize():
                log.info('Container key will be preauthorized')
            else:
                ret['comment'] = 'Container key preauthorization failed'
                ret['result'] = False
                return ret

    log.info('Creating container(s) \'{0}\''
             ' on host \'{1}\''.format(names, host))

    cmds = []
    for name in names:
        args = [name]
        kw = kwargs
        if saltcloud_mode:
            kw = copy.deepcopy(kw)
            kw['name'] = name
            kw = client.cmd(
                host, 'lxc.cloud_init_interface', args + [kw],
                expr_form='list', timeout=600).get(host, {})
        name = kw.pop('name', name)
        # be sure not to seed an alrady seeded host
        kw['seed'] = seeds[name]
        if not kw['seed']:
            kw.pop('seed_cmd', '')
        cmds.append(
            (host,
             name,
             client.cmd_iter(host, 'lxc.init', args, kwarg=kw, timeout=600)))
    done = ret.setdefault('done', [])
    errors = ret.setdefault('errors', OrderedDict())

    for ix, acmd in enumerate(cmds):
        hst, container_name, cmd = acmd
        containers = ret.setdefault(hst, [])
        herrs = errors.setdefault(hst, OrderedDict())
        serrs = herrs.setdefault(container_name, [])
        sub_ret = next(cmd)
        error = None
        if isinstance(sub_ret, dict) and host in sub_ret:
            j_ret = sub_ret[hst]
            container = j_ret.get('ret', {})
            if container and isinstance(container, dict):
                if not container.get('result', False):
                    error = container
            else:
                error = 'Invalid return for {0}'.format(container_name)
        else:
            error = sub_ret
            if not error:
                error = 'unknown error (no return)'
        if error:
            ret['result'] = False
            serrs.append(error)
        else:
            container['container_name'] = name
            containers.append(container)
            done.append(container)

    # marking ping status as True only and only if we have at
    # least provisioned one container
    ret['ping_status'] = bool(len(done))

    # for all provisioned containers, last job is to verify
    # - the key status
    # - we can reach them
    for container in done:
        # explicitly check and update
        # the minion key/pair stored on the master
        container_name = container['container_name']
        key = os.path.join(__opts__['pki_dir'], 'minions', container_name)
        if explicit_auth:
            fcontent = ''
            if os.path.exists(key):
                with open(key) as fic:
                    fcontent = fic.read().strip()
            if pub_key.strip() != fcontent:
                with open(key, 'w') as fic:
                    fic.write(pub_key)
                    fic.flush()
        mid = j_ret.get('mid', None)
        if not mid:
            continue

        def testping(**kw):
            mid_ = kw['mid']
            ping = client.cmd(mid_, 'test.ping', timeout=20)
            time.sleep(1)
            if ping:
                return 'OK'
            raise Exception('Unresponsive {0}'.format(mid_))
        ping = salt.utils.cloud.wait_for_fun(testping, timeout=21, mid=mid)
        if ping != 'OK':
            ret['ping_status'] = False
            ret['result'] = False

    # if no lxc detected as touched (either inited or verified
    # we result to False
    if not done:
        ret['result'] = False
    if not quiet:
        salt.output.display_output(ret, '', __opts__)
    return ret


def cloud_init(names, host=None, quiet=False, **kwargs):
    '''
    Wrapper for using lxc.init in saltcloud compatibility mode

    names
        Name of the containers, supports a single name or a comma delimited
        list of names.

    host
        Minion to start the container on. Required.

    saltcloud_mode
        init the container with the saltcloud opts format instead
    '''
    return __salt__['lxc.init'](names=names, host=host,
                                saltcloud_mode=True, quiet=quiet, **kwargs)


def _list_iter(host=None):
    '''
    Return a generator iterating over hosts
    '''
    tgt = host or '*'
    client = salt.client.get_local_client(__opts__['conf_file'])
    for container_info in client.cmd_iter(tgt, 'lxc.list'):
        if not container_info:
            continue
        if not isinstance(container_info, dict):
            continue
        chunk = {}
        id_ = container_info.keys()[0]
        if host and host != id_:
            continue
        if not isinstance(container_info[id_], dict):
            continue
        if 'ret' not in container_info[id_]:
            continue
        if not isinstance(container_info[id_]['ret'], dict):
            continue
        chunk[id_] = container_info[id_]['ret']
        yield chunk


def list_(host=None, quiet=False):
    '''
    List defined containers (running, stopped, and frozen) for the named
    (or all) host(s).

    .. code-block:: bash

        salt-run lxc.list [host=minion_id]
    '''
    it = _list_iter(host)
    ret = {}
    for chunk in it:
        ret.update(chunk)
        if not quiet:
            salt.output.display_output(chunk, 'lxc_list', __opts__)
    return ret


def purge(name, delete_key=True, quiet=False):
    '''
    Purge the named container and delete its minion key if present.
    WARNING: Destroys all data associated with the container.

    .. code-block:: bash

        salt-run lxc.purge name
    '''
    data = _do_names(name, 'destroy')
    if data is False:
        return data

    if delete_key:
        skey = salt.key.Key(__opts__)
        skey.delete_key(name)

    if data is None:
        return

    if not quiet:
        salt.output.display_output(data, 'lxc_purge', __opts__)
    return data


def start(name, quiet=False):
    '''
    Start the named container.

    .. code-block:: bash

        salt-run lxc.start name
    '''
    data = _do_names(name, 'start')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_start', __opts__)
    return data


def stop(name, quiet=False):
    '''
    Stop the named container.

    .. code-block:: bash

        salt-run lxc.stop name
    '''
    data = _do_names(name, 'stop')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_force_off', __opts__)
    return data


def freeze(name, quiet=False):
    '''
    Freeze the named container

    .. code-block:: bash

        salt-run lxc.freeze name
    '''
    data = _do_names(name, 'freeze')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_pause', __opts__)
    return data


def unfreeze(name, quiet=False):
    '''
    Unfreeze the named container

    .. code-block:: bash

        salt-run lxc.unfreeze name
    '''
    data = _do_names(name, 'unfreeze')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_resume', __opts__)
    return data


def info(name, quiet=False):
    '''
    Returns information about a container.

    .. code-block:: bash

        salt-run lxc.info name
    '''
    data = _do_names(name, 'info')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_info', __opts__)
    return data
