# -*- coding: utf-8 -*-
'''
Work with linux containers

:depends: lxc package for distribution
'''

# Import python libs
import logging
import tempfile
import os

#import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    if not salt.utils.which('lxc'):
        return False
    return 'lxc'


def _lxc_profile(profile):
    '''
    Gather the lxc profile from the config or apply the default (empty).

    Profiles can be defined in the config or pillar, e.g.:

    .. code-block:: yaml

        lxc.profile:
          ubuntu:
            template: ubuntu
            backing: lvm
            vgname: lxc
            size: 1G
    '''
    return __salt__['config.option']('lxc.profile', {}).get(profile, {})


def _nic_profile(nic):
    '''
    Gather the nic profile from the config or apply the default.

    This is the ``default`` profile, which can be overridden in the
    configuration:

    .. code-block:: yaml

        lxc.nic:
          default:
            eth0:
              link: br0
              type: veth
    '''
    default = {'eth0': {'link': 'br0', 'type': 'veth'}}
    return __salt__['config.option']('lxc.nic', {}).get(nic, default)


def _gen_config(nicp,
                cpuset=None,
                cpushare=None,
                memory=None,
                nic_opts=None):
    '''
    Generate the config string for an lxc container
    '''
    data = []

    if memory:
        data.append(('lxc.cgroup.memory.limit_in_bytes', memory * 1024 * 1024))
    if cpuset:
        data.append(('lxc.cgroup.cpuset.cpus', cpuset))
    if cpushare:
        data.append(('lxc.cgroup.cpu.shares', cpushare))

    for dev, args in nicp.items():
        data.append(('lxc.network.type', args.pop('type', 'veth')))
        data.append(('lxc.network.name', dev))
        data.append(('lxc.network.flags', args.pop('flags', 'up')))
        opts = nic_opts.get(dev) if nic_opts else None
        if opts:
            mac = opts.get('mac')
            ipv4 = opts.get('ipv4')
            ipv6 = opts.get('ipv6')
        else:
            ipv4, ipv6 = None, None
            mac = salt.utils.gen_mac()
        data.append(('lxc.network.hwaddr', mac))
        if ipv4:
            data.append(('lxc.network.ipv4', ipv4))
        if ipv6:
            data.append(('lxc.network.ipv6', ipv6))
        for k, v in args.items():
            data.append(('lxc.network.{0}'.format(k), v))

    return '\n'.join(['{0} = {1}'.format(k, v) for k, v in data]) + '\n'


def init(name,
         cpuset=None,
         cpushare=None,
         memory=None,
         nic='default',
         profile=None,
         nic_opts=None,
         **kwargs):
    '''
    Initialize a new container.

    .. code-block:: bash

        salt 'minion' lxc.init name [cpuset=cgroups_cpuset] \\
                [cpushare=cgroups_cpushare] [memory=cgroups_memory] \\
                [nic=nic_profile] [profile=lxc_profile] \\
                [nic_opts=nic_opts] [start=(true|false)] \\
                [seed=(true|false)] [install=(true|false)] \\
                [config=minion_config]

    name
        Name of the container.

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
        Seed the container with the minion config. Default: true

    install
        If salt-minion is not already installed, install it. Default: true

    config
        Optional config paramers. By default, the id is set to the name of the
        container.
    '''
    nicp = _nic_profile(nic)
    start_ = kwargs.pop('start', False)
    seed = kwargs.pop('seed', True)
    install = kwargs.pop('install', True)
    seed_cmd = kwargs.pop('seed_cmd', None)
    config = kwargs.pop('config', None)

    with tempfile.NamedTemporaryFile() as cfile:
        cfile.write(_gen_config(cpuset=cpuset, cpushare=cpushare,
                                memory=memory, nicp=nicp, nic_opts=nic_opts))
        cfile.flush()
        ret = create(name, config=cfile.name, profile=profile, **kwargs)
    if not ret['created']:
        return ret
    rootfs = info(name)['rootfs']
    if seed:
        __salt__['seed.apply'](rootfs, id_=name, config=config,
                               install=install)
    elif seed_cmd:
        __salt__[seed_cmd](rootfs, name, config)
    if start_ and ret['created']:
        ret['state'] = start(name)['state']
    else:
        ret['state'] = state(name)
    return ret


def create(name, config=None, profile=None, options=None, **kwargs):
    '''
    Create a new container.

    .. code-block:: bash

        salt 'minion' lxc.create name [config=config_file] \\
                [profile=profile] [template=template_name] \\
                [backing=backing_store] [ vgname=volume_group] \\
                [size=filesystem_size] [options=template_options]

    name
        Name of the container.

    config
        The config file to use for the container. Defaults to system-wide
        config (usually in /etc/lxc/lxc.conf).

    profile
        A LXC profile (defined in config or pillar).

    template
        The template to use. E.g., 'ubuntu' or 'fedora'.

    backing
        The type of storage to use. Set to 'lvm' to use an LVM group. Defaults
        to filesystem within /var/lib/lxc/.

    vgname
        Name of the LVM volume group in which to create the volume for this
        container. Only applicable if backing=lvm. Defaults to 'lxc'.

    size
        Size of the volume to create. Only applicable if backing=lvm.
        Defaults to 1G.

    options
        Template specific options to pass to the lxc-create command.
    '''

    if exists(name):
        return {'created': False, 'error': 'container already exists'}

    cmd = 'lxc-create -n {0}'.format(name)

    profile = _lxc_profile(profile)

    def select(k, default=None):
        kw = kwargs.pop(k, None)
        p = profile.pop(k, default)
        return kw or p

    template = select('template')
    backing = select('backing')
    vgname = select('vgname')
    size = select('size', '1G')

    if config:
        cmd += ' -f {0}'.format(config)
    if template:
        cmd += ' -t {0}'.format(template)
    if backing:
        cmd += ' -B {0}'.format(backing)
        if vgname:
            cmd += ' --vgname {0}'.format(vgname)
        if size:
            cmd += ' --fssize {0}'.format(size)
    if profile:
        cmd += ' --'
        options = profile
        for k, v in options.items():
            cmd += ' --{0} {1}'.format(k, v)

    ret = __salt__['cmd.run_all'](cmd)
    if ret['retcode'] == 0 and exists(name):
        return {'created': True}
    else:
        if exists(name):
            # destroy the container if it was partially created
            cmd = 'lxc-destroy -n {0}'.format(name)
            __salt__['cmd.retcode'](cmd)
        log.warn('lxc-create failed to create container')
        return {'created': False, 'error':
                'container could not be created: {0}'.format(ret['stderr'])}


def list_():
    '''
    List defined containers (running, stopped, and frozen).

    .. code-block:: bash

        salt '*' lxc.list
    '''
    ret = __salt__['cmd.run']('lxc-list').splitlines()

    stopped = []
    frozen = []
    running = []
    current = None

    for l in ret:
        l = l.strip()
        if not len(l):
            continue
        if l == 'STOPPED':
            current = stopped
            continue
        if l == 'FROZEN':
            current = frozen
            continue
        if l == 'RUNNING':
            current = running
            continue
        current.append(l)
    return {'running': running,
            'stopped': stopped,
            'frozen': frozen}


def _change_state(cmd, name, expected):
    s1 = state(name)
    if s1 is None:
        return {'state': None, 'change': False}
    elif s1 == expected:
        return {'state': expected, 'change': False}

    cmd = '{0} -n {1}'.format(cmd, name)
    err = __salt__['cmd.run_stderr'](cmd)
    if err:
        s2 = state(name)
        r = {'state': s2, 'change': s1 != s2, 'error': err}
    else:
        if expected is not None:
            # some commands do not wait, so we will
            cmd = 'lxc-wait -n {0} -s {1}'.format(name, expected.upper())
            __salt__['cmd.run'](cmd, timeout=30)
        s2 = state(name)
        r = {'state': s2, 'change': s1 != s2}
    return r


def start(name):
    '''
    Start the named container.

    .. code-block:: bash

        salt '*' lxc.start name
    '''
    return _change_state('lxc-start -d', name, 'running')


def stop(name):
    '''
    Stop the named container.

    .. code-block:: bash

        salt '*' lxc.stop name
    '''
    return _change_state('lxc-stop', name, 'stopped')


def freeze(name):
    '''
    Freeze the named container.

    .. code-block:: bash

        salt '*' lxc.freeze name
    '''
    return _change_state('lxc-freeze', name, 'frozen')


def unfreeze(name):
    '''
    Unfreeze the named container.

    .. code-block:: bash

        salt '*' lxc.unfreeze name
    '''
    return _change_state('lxc-unfreeze', name, 'running')


def destroy(name, stop=True):
    '''
    Destroy the named container.
    WARNING: Destroys all data associated with the container.

    .. code-block:: bash

        salt '*' lxc.destroy name [stop=(true|false)]
    '''
    if stop:
        _change_state('lxc-stop', name, 'stopped')
    return _change_state('lxc-destroy', name, None)


def exists(name):
    '''
    Returns whether the named container exists.

    .. code-block:: bash

        salt '*' lxc.exists name
    '''
    l = list_()
    return name in (l['running'] + l['stopped'] + l['frozen'])


def state(name):
    '''
    Returns the state of a container.

    .. code-block:: bash

        salt '*' lxc.state name
    '''
    if not exists(name):
        return None

    cmd = 'lxc-info -n {0}'.format(name)
    ret = __salt__['cmd.run_all'](cmd)
    if ret['retcode'] != 0:
        return False
    else:
        lines = ret['stdout'].splitlines()
        r = dict([l.split() for l in lines])
        return r['state:'].lower()


def get_parameter(name, parameter):
    '''
    Returns the value of a cgroup parameter for a container.

    .. code-block:: bash

        salt '*' lxc.get_parameter name parameter
    '''
    if not exists(name):
        return None

    cmd = 'lxc-cgroup -n {0} {1}'.format(name, parameter)
    ret = __salt__['cmd.run_all'](cmd)
    if ret['retcode'] != 0:
        return False
    else:
        return {parameter: ret['stdout'].strip()}


def set_parameter(name, parameter, value):
    '''
    Set the value of a cgroup parameter for a container.

    .. code-block:: bash

        salt '*' lxc.set_parameter name parameter value
    '''
    if not exists(name):
        return None

    cmd = 'lxc-cgroup -n {0} {1} {2}'.format(name, parameter, value)
    ret = __salt__['cmd.run_all'](cmd)
    if ret['retcode'] != 0:
        return False
    else:
        return True


def info(name):
    '''
    Returns information about a container.

    .. code-block:: bash

        salt '*' lxc.info name
    '''
    f = '/var/lib/lxc/{0}/config'.format(name)
    if not os.path.isfile(f):
        return None

    ret = {}

    config = [(v[0].strip(), v[1].strip()) for v in
              [l.split('#', 1)[0].strip().split('=', 1) for l in
               open(f).readlines()] if len(v) == 2]

    ifaces = []
    current = None

    for k, v in config:
        if k == 'lxc.network.type':
            current = {'type': v}
            ifaces.append(current)
        elif not current:
            continue
        elif k.startswith('lxc.network.'):
            current[k.replace('lxc.network.', '', 1)] = v
    if ifaces:
        ret['nics'] = ifaces

    ret['rootfs'] = next((i[1] for i in config if i[0] == 'lxc.rootfs'), None)
    ret['state'] = state(name)

    if ret['state'] == 'running':
        limit = int(get_parameter(name, 'memory.limit_in_bytes').get(
            'memory.limit_in_bytes'))
        usage = int(get_parameter(name, 'memory.usage_in_bytes').get(
            'memory.usage_in_bytes'))
        free = limit - usage
        ret['memory_limit'] = limit
        ret['memory_free'] = free

    return ret
