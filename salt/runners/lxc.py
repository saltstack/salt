# -*- coding: utf-8 -*-
'''
Control Linux Containers via Salt

:depends: lxc execution module
'''

# Import python libs
from __future__ import print_function

# Import Salt libs
import salt.client
import salt.utils.virt
import salt.key


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

    client = salt.client.LocalClient(__opts__['conf_file'])
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


def find_guest(name, quiet=False):
    '''
    Returns the host for a container.

    .. code-block:: bash

        salt-run lxc.find_guest name
    '''
    data = list_(quiet=True)

    for host, l in data.items():
        # Check if data is a dict, and not '"virt.full_info" is not available.'
        if not isinstance(l, dict):
            continue
        for x in 'running', 'frozen', 'stopped':
            if name in l[x]:
                if not quiet:
                    salt.output.display_output(
                            host,
                            'lxc_find_host',
                            __opts__)
                return host
    return None


def init(name,
         host=None,
         **kwargs):
    '''
    Initialize a new container

    .. code-block:: bash

        salt-run lxc.init name host=minion_id [cpuset=cgroups_cpuset] \\
                [cpushare=cgroups_cpushare] [memory=cgroups_memory] \\
                [nic=nic_profile] [profile=lxc_profile] \\
                [nic_opts=nic_opts] [start=(true|false)] \\
                [seed=(true|false)] [install=(true|false)] \\
                [config=minion_config]

    name
        Name of the container.

    host
        Minion to start the container on. Required.

    cpuset
        cgroups cpuset.

    cpushare
        cgroups cpu shares.

    memory
        cgroups memory limit, in MB.

    nic
        Network interfaces profile (defined in config or pillar).

    profile
        A LXC profile (defined in config or pillar).

    nic_opts
        Extra options for network interfaces. E.g:
        {"eth0": {"mac": "aa:bb:cc:dd:ee:ff", "ipv4": "10.1.1.1", "ipv6": "2001:db8::ff00:42:8329"}}

    start
        Start the newly created container.

    seed
        Seed the container with the minion config and autosign its key. Default: true

    install
        If salt-minion is not already installed, install it. Default: true

    config
        Optional config paramers. By default, the id is set to the name of the
        container.
    '''
    print('Searching for LXC Hosts')
    data = __salt__['lxc.list'](host, quiet=True)
    for host, containers in data.items():
        if name in sum(containers.values(), []):
            print('Container "{0}" is already deployed'.format(name))
            return 'fail'

    if host is None:
        #TODO: Support selection of host based on available memory/cpu/etc.
        print('A host must be provided.')
        return 'fail'

    if host not in data:
        print('Host "{0}" was not found'.format(host))
        return 'fail'

    seed = kwargs.get('seed', True)
    if seed:
        kv = salt.utils.virt.VirtKey(host, name, __opts__)
        if kv.authorize():
            print('Minion will be preseeded.')
        else:
            print('Preauthorization failed.')
            return 'fail'

    client = salt.client.LocalClient(__opts__['conf_file'])

    print('Creating container {0} on host {1}.'.format(name, host))
    args = [name]

    cmd_ret = client.cmd_iter(host,
                              'lxc.init',
                              args,
                              kwarg=kwargs,
                              timeout=600)

    ret = next(cmd_ret)
    if not ret:
        print('Container {0} was not initialized.'.format(name))
        return 'fail'

    print('Container {0} initialized on host {1}'.format(name, host))
    return 'good'


def list_(host=None, quiet=False):
    '''
    List defined containers (running, stopped, and frozen) for the named
    (or all) host(s).

    .. code-block:: bash

        salt-run lxc.list [host=minion_id]
    '''

    tgt = host or '*'
    ret = {}
    client = salt.client.LocalClient(__opts__['conf_file'])
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

    data = _do(name, 'destroy')
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
    data = _do(name, 'start')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_start', __opts__)
    return data


def stop(name, quiet=False):
    '''
    Stop the named container.

    .. code-block:: bash

        salt-run lxc.stop name
    '''
    data = _do(name, 'stop')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_force_off', __opts__)
    return data


def freeze(name, quiet=False):
    '''
    Freeze the named container

    .. code-block:: bash

        salt-run lxc.freeze name
    '''
    data = _do(name, 'freeze')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_pause', __opts__)
    return data


def unfreeze(name, quiet=False):
    '''
    Unfreeze the named container

    .. code-block:: bash

        salt-run lxc.unfreeze name
    '''
    data = _do(name, 'unfreeze')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_resume', __opts__)
    return data


def info(name, quiet=False):
    '''
    Returns information about a container.

    .. code-block:: bash

        salt-run lxc.info name
    '''
    data = _do(name, 'info')
    if data and not quiet:
        salt.output.display_output(data, 'lxc_info', __opts__)
    return data
