# -*- coding: utf-8 -*-
'''
Control Linux Containers via Salt

:depends: lxc package for distribution

You need lxc >= 1.0 (even beta alpha)

'''

# Import python libs
from __future__ import print_function
import traceback
import datetime
import pipes
import logging
import tempfile
import os
import shutil
import re

#import salt libs
import salt.utils
import salt.utils.cloud
import salt.config

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}


DEFAULT_NIC_PROFILE = {'eth0': {'link': 'br0', 'type': 'veth'}}


def _ip_sort(ip):
    '''Ip sorting'''
    idx = '001'
    if ip == '127.0.0.1':
        idx = '200'
    if ip == '::1':
        idx = '201'
    elif '::' in ip:
        idx = '100'
    return '{0}___{1}'.format(idx, ip)


def __virtual__():
    if salt.utils.which('lxc-start'):
        return True
    # To speed up the whole thing, we decided to not use the
    # subshell way and assume things are in place for lxc
    # Discussion made by @kiorky and @thatch45

    # lxc-version presence is not sufficient, in lxc1.0 alpha
    # (precise backports), we have it and it is sufficient
    # for the module to execute.
    # elif salt.utils.which('lxc-version'):
    #     passed = False
    #     try:
    #         passed = subprocess.check_output(
    #             'lxc-version').split(':')[1].strip() >= '1.0'
    #     except Exception:
    #         pass
    #     if not passed:
    #         log.warning('Support for lxc < 1.0 may be incomplete.')
    #     return 'lxc'
    # return False
    #
    return False


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


class _LXCConfig(object):
    '''
    LXC configuration data
    '''
    pattern = re.compile(r'^(\S+)(\s*)(=)(\s*)(.*)')

    def __init__(self, **kwargs):
        self.name = kwargs.pop('name', None)
        self.data = []
        if self.name:
            self.path = '/var/lib/lxc/{0}/config'.format(self.name)
            if os.path.isfile(self.path):
                with open(self.path) as f:
                    for l in f.readlines():
                        match = self.pattern.findall((l.strip()))
                        if match:
                            self.data.append((match[0][0], match[0][-1]))
        else:
            self.path = None

        def _replace(k, v):
            if v:
                self._filter_data(k)
                self.data.append((k, v))

        memory = kwargs.pop('memory', None)
        if memory:
            memory = memory * 1024 * 1024
        _replace('lxc.cgroup.memory.limit_in_bytes', memory)
        cpuset = kwargs.pop('cpuset', None)
        _replace('lxc.cgroup.cpuset.cpus', cpuset)
        cpushare = kwargs.pop('cpushare', None)
        _replace('lxc.cgroup.cpu.shares', cpushare)

        nic = kwargs.pop('nic')
        if nic:
            self._filter_data('lxc.network')
            nicp = __salt__['config.option']('lxc.nic', {}).get(
                        nic, DEFAULT_NIC_PROFILE
                    )
            nic_opts = kwargs.pop('nic_opts', None)

            for dev, args in nicp.items():
                self.data.append(('lxc.network.type',
                                  args.pop('type', 'veth')))
                self.data.append(('lxc.network.name', dev))
                self.data.append(('lxc.network.flags',
                                  args.pop('flags', 'up')))
                opts = nic_opts.get(dev) if nic_opts else None
                if opts:
                    mac = opts.get('mac')
                    ipv4 = opts.get('ipv4')
                    ipv6 = opts.get('ipv6')
                else:
                    ipv4, ipv6 = None, None
                    mac = salt.utils.gen_mac()
                self.data.append(('lxc.network.hwaddr', mac))
                if ipv4:
                    self.data.append(('lxc.network.ipv4', ipv4))
                if ipv6:
                    self.data.append(('lxc.network.ipv6', ipv6))
                for k, v in args.items():
                    self.data.append(('lxc.network.{0}'.format(k), v))

    def as_string(self):
        return '\n'.join(
                ['{0} = {1}'.format(k, v) for k, v in self.data]) + '\n'

    def write(self):
        if self.path:
            salt.utils.fopen(self.path, 'w').write(self.as_string())

    def tempfile(self):
        # this might look like the function name is shadowing the
        # module, but it's not since the method belongs to the class
        f = tempfile.NamedTemporaryFile()
        f.write(self.as_string())
        f.flush()
        return f

    def _filter_data(self, pat):
        x = []
        for i in self.data:
            if not re.match('^' + pat, i[0]):
                x.append(i)
        self.data = x


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

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.init name [cpuset=cgroups_cpuset] \\
                [cpushare=cgroups_cpushare] [memory=cgroups_memory] \\
                [nic=nic_profile] [profile=lxc_profile] \\
                [nic_opts=nic_opts] [start=(True|False)] \\
                [seed=(True|False)] [install=(True|False)] \\
                [config=minion_config] [approve_key=(True|False) \\
                [clone=original]

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
        Seed the container with the minion config. Default: ``True``

    install
        If salt-minion is not already installed, install it. Default: ``True``

    config
        Optional config parameters. By default, the id is set to the name of the
        container.

    approve_key
        Attempt to request key approval from the master. Default: ``True``

    clone
        Original from which to use a clone operation to create the container. Default: ``None``
    '''
    profile = _lxc_profile(profile)

    def select(k, default=None):
        kw = kwargs.pop(k, None)
        p = profile.pop(k, default)
        return kw or p

    start_ = select('start', False)
    seed = select('seed', True)
    install = select('install', True)
    seed_cmd = select('seed_cmd')
    salt_config = select('config')
    approve_key = select('approve_key', True)
    clone_from = select('clone')

    if clone_from:
        ret = __salt__['lxc.clone'](name, clone_from,
                                    profile=profile, **kwargs)
        if not ret.get('cloned', False):
            return ret
        cfg = _LXCConfig(name=name, nic=nic, nic_opts=nic_opts,
                        cpuset=cpuset, cpushare=cpushare, memory=memory)
        cfg.write()
    else:
        cfg = _LXCConfig(nic=nic, nic_opts=nic_opts, cpuset=cpuset,
                        cpushare=cpushare, memory=memory)
        with cfg.tempfile() as cfile:
            ret = __salt__['lxc.create'](name, config=cfile.name,
                                         profile=profile, **kwargs)
        if not ret.get('created', False):
            return ret
    rootfs = info(name)['rootfs']
    if seed:
        ret['seeded'] = __salt__['lxc.bootstrap'](
            name, config=salt_config, approve_key=approve_key, install=install)
    elif seed_cmd:
        ret['seeded'] = __salt__[seed_cmd](rootfs, name, salt_config)
    if start_:
        ret['state'] = start(name)['state']
    else:
        ret['state'] = state(name)
    return ret


def create(name, config=None, profile=None, options=None, **kwargs):
    '''
    Create a new container.

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.create name [config=config_file] \\
                [profile=profile] [template=template_name] \\
                [backing=backing_store] [vgname=volume_group] \\
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

    fstype
        fstype to use on LVM lv.

    size
        Size of the volume to create. Only applicable if backing=lvm.
        Defaults to 1G.

    options
        Template specific options to pass to the lxc-create command.
    '''

    if exists(name):
        return {'created': False, 'error': 'container already exists'}

    cmd = 'lxc-create -n {0}'.format(name)

    if not isinstance(profile, dict):
        profile = _lxc_profile(profile)

    def select(k, default=None):
        kw = kwargs.pop(k, None)
        p = profile.pop(k, default)
        return kw or p

    template = select('template')
    backing = select('backing')
    lvname = select('lvname')
    fstype = select('fstype')
    vgname = select('vgname')
    size = select('size', '1G')

    if config:
        cmd += ' -f {0}'.format(config)
    if template:
        cmd += ' -t {0}'.format(template)
    if backing:
        backing = backing.lower()
        cmd += ' -B {0}'.format(backing)
        if backing in ['lvm']:
            if lvname:
                cmd += ' --lvname {0}'.format(vgname)
            if vgname:
                cmd += ' --vgname {0}'.format(vgname)
        if backing not in ['dir', 'overlayfs']:
            if fstype:
                cmd += ' --fstype {0}'.format(fstype)
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


def clone(name,
          orig,
          snapshot=False,
          profile=None,
          **kwargs):

    '''
    Create a new container.

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.clone name orig [snapshot=(True|False)] \\
                [size=filesystem_size] [vgname=volume_group] \\
                [profile=profile_name]

    name
        Name of the container.

    orig
        Name of the cloned original container

    snapshot
        Do we use Copy On Write snapshots (LVM)

    size
        Size of the container

    vgname
        LVM volume group(lxc)

    profile
        A LXC profile (defined in config or pillar).

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.clone myclone ubuntu "snapshot=True"

    '''

    if exists(name):
        return {'cloned': False, 'error': 'container already exists'}

    orig_state = state(orig)
    if orig_state is None:
        return {'cloned': False,
                'error':
                'original container \'{0}\' does not exist'.format(orig)}
    elif orig_state != 'stopped':
        return {'cloned': False,
                'error': 'original container \'{0}\' is running'.format(orig)}

    if not snapshot:
        snapshot = ''
    else:
        snapshot = '-s'
    cmd = 'lxc-clone {2} -o {0} -n {1}'.format(orig, name, snapshot)

    if not isinstance(profile, dict):
        profile = _lxc_profile(profile)

    def select(k, default=None):
        kw = kwargs.pop(k, None)
        p = profile.pop(k, default)
        return kw or p

    backing = select('backing')
    size = select('size', '1G')

    if size:
        cmd += ' -L {0}'.format(size)
    if backing:
        cmd += ' -B {0}'.format(backing)

    ret = __salt__['cmd.run_all'](cmd)
    if ret['retcode'] == 0 and exists(name):
        return {'cloned': True}
    else:
        if exists(name):
            # destroy the container if it was partially created
            cmd = 'lxc-destroy -n {0}'.format(name)
            __salt__['cmd.retcode'](cmd)
        log.warn('lxc-clone failed to create container')
        return {'cloned': False, 'error':
                'container could not be created: {0}'.format(ret['stderr'])}


def list_(extra=False):
    '''
    List defined containers classified by status.
    Status can be running, stopped, and frozen.

        extra
            Also get per container specific info at once.
            Warning: it will not return a collection of list
            but a collection of mappings by status and then per
            container name::

                {'running': ['foo']} # normal mode
                {'running': {'foo': {'info1': 'bar'}} # extra mode

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.list
        salt '*' lxc.list extra=True
    '''
    ctnrs = __salt__['cmd.run']('lxc-ls | sort -u').splitlines()

    if extra:
        stopped = {}
        frozen = {}
        running = {}
    else:
        stopped = []
        frozen = []
        running = []

    ret = {'running': running,
           'stopped': stopped,
           'frozen': frozen}

    for container in ctnrs:
        c_infos = __salt__['cmd.run'](
                'lxc-info -n {0}'.format(container)).splitlines()
        log.debug(c_infos)
        c_state = None
        for c_info in c_infos:
            log.debug(c_info)
            stat = c_info.split(':')
            if stat[0] in ('State', 'state'):
                c_state = stat[1].strip()
                break
        if extra:
            try:
                infos = __salt__['lxc.info'](container)
            except Exception:
                trace = traceback.format_exc()
                infos = {'error': 'Error while getting extra infos',
                         'comment': trace}
            method = 'update'
            value = {container: infos}
        else:
            method = 'append'
            value = container

        if not c_state:
            continue
        if c_state == 'STOPPED':
            getattr(stopped, method)(value)
            continue
        if c_state == 'FROZEN':
            getattr(frozen, method)(value)
            continue
        if c_state == 'RUNNING':
            getattr(running, method)(value)
            continue
    return ret


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


def _ensure_running(name, no_start=False):
    prior_state = __salt__['lxc.state'](name)
    if not prior_state:
        return None
    res = {}
    if prior_state == 'stopped':
        if no_start:
            return False
        res = __salt__['lxc.start'](name)
    elif prior_state == 'frozen':
        if no_start:
            return False
        res = __salt__['lxc.unfreeze'](name)
    if res.get('error'):
        log.warn('Failed to run command: {0}'.format(res['error']))
        return False
    return prior_state


def start(name, restart=False):
    '''
    Start the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.start name
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Started'}
    try:
        does_exist = __salt__['lxc.exists'](name)
        if not does_exist:
            return {'name': name,
                    'result': False,
                    'comment': 'Container does not exist'}
        if restart:
            __salt__['lxc.stop'](name)
        ret.update(_change_state('lxc-start -d', name, 'running'))
        infos = __salt__['lxc.info'](name)
        ret['result'] = infos['state'] == 'running'
        if ret['change']:
            ret['changes']['started'] = 'started'
    except Exception, ex:
        trace = traceback.format_exc()
        ret['result'] = False
        ret['comment'] = 'Error in starting container'
        ret['comment'] += '{0}\n{1}\n'.format(ex, trace)
    return ret


def stop(name):
    '''
    Stop the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.stop name
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Stopped'}
    try:
        does_exist = __salt__['lxc.exists'](name)
        if not does_exist:
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'Container does not exist'}
        ret.update(_change_state('lxc-stop', name, 'stopped'))
        infos = __salt__['lxc.info'](name)
        ret['result'] = infos['state'] == 'stopped'
        if ret['change']:
            ret['changes']['stopped'] = 'stopped'
    except Exception, ex:
        trace = traceback.format_exc()
        ret['result'] = False
        ret['comment'] = 'Error in stopping container'
        ret['comment'] += '{0}\n{1}\n'.format(ex, trace)
    return ret


def freeze(name):
    '''
    Freeze the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.freeze name
    '''
    return _change_state('lxc-freeze', name, 'frozen')


def unfreeze(name):
    '''
    Unfreeze the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.unfreeze name
    '''
    return _change_state('lxc-unfreeze', name, 'running')


def destroy(name, stop=True):
    '''
    Destroy the named container.
    WARNING: Destroys all data associated with the container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.destroy name [stop=(True|False)]
    '''
    if stop:
        _change_state('lxc-stop', name, 'stopped')
    return _change_state('lxc-destroy', name, None)


def exists(name):
    '''
    Returns whether the named container exists.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.exists name
    '''
    l = list_()
    return name in l['running'] + l['stopped'] + l['frozen']


def state(name):
    '''
    Returns the state of a container.

    CLI Example:

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
        c_infos = ret['stdout'].splitlines()
        c_state = None
        for c_info in c_infos:
            stat = c_info.split(':')
            if stat[0] in ('State', 'state'):
                c_state = stat[1].strip().lower()
                break
        return c_state


def get_parameter(name, parameter):
    '''
    Returns the value of a cgroup parameter for a container.

    CLI Example:

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

    CLI Example:

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


def templates(templates_dir='/usr/share/lxc/templates'):
    '''
    Returns a list of existing templates

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.templates
    '''
    templates_list = []
    san = re.compile('^lxc-')
    if os.path.isdir(templates_dir):
        templates_list.extend(
            [san.sub('', a) for a in os.listdir(templates_dir)]
        )
    templates_list.sort()
    return templates_list


def info(name):
    '''
    Returns information about a container.

    CLI Example:

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
    ret['_ips'] = []
    ret['public_ips'] = []
    ret['private_ips'] = []
    ret['public_ipv4_ips'] = []
    ret['public_ipv6_ips'] = []
    ret['private_ipv4_ips'] = []
    ret['private_ipv6_ips'] = []
    ret['ipv4_ips'] = []
    ret['ipv6_ips'] = []
    ret['size'] = None

    if ret['state'] == 'running':
        limit = int(get_parameter(name, 'memory.limit_in_bytes').get(
            'memory.limit_in_bytes'))
        usage = int(get_parameter(name, 'memory.usage_in_bytes').get(
            'memory.usage_in_bytes'))
        free = limit - usage
        ret['memory_limit'] = limit
        ret['memory_free'] = free
        ret['size'] = __salt__['cmd.run'](
            ('lxc-attach -n \'{0}\' -- '
             'df /|tail -n1|awk \'{{print $2}}\'').format(name))
        ipaddr = __salt__['cmd.run'](
            'lxc-attach -n \'{0}\' -- ip addr show'.format(name))
        for line in ipaddr.splitlines():
            if 'inet' in line:
                line = line.split()
                ip_address = line[1].split('/')[0]
                if not ip_address in ret['_ips']:
                    ret['_ips'].append(ip_address)
                    if '::' in ip_address:
                        ret['ipv6_ips'].append(ip_address)
                        if (
                            ip_address == '::1'
                            or ip_address.startswith('fe80')
                        ):
                            ret['private_ips'].append(ip_address)
                            ret['private_ipv6_ips'].append(ip_address)
                        else:
                            ret['public_ips'].append(ip_address)
                            ret['public_ipv6_ips'].append(ip_address)
                    else:
                        ret['ipv4_ips'].append(ip_address)
                        if ip_address == '127.0.0.1':
                            ret['private_ips'].append(ip_address)
                            ret['private_ipv4_ips'].append(ip_address)
                        elif salt.utils.cloud.is_public_ip(ip_address):
                            ret['public_ips'].append(ip_address)
                            ret['public_ipv4_ips'].append(ip_address)
                        else:
                            ret['private_ips'].append(ip_address)
                            ret['private_ipv4_ips'].append(ip_address)
    for k in [l for l in ret if l.endswith('_ips')]:
        ret[k].sort(key=_ip_sort)
    return ret


def set_pass(name, users, password):
    '''Set the password of one or more system users inside containers

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.set_pass root foo
    '''
    ret = {'result': True, 'comment': ''}
    if not isinstance(users, list):
        users = [users]
    ret['comment'] = ''
    if users:
        try:
            cmd = (
                "lxc-attach -n \"{0}\" -- "
                " /bin/sh -c \""
                "").format(name)
            for i in users:
                cmd += "echo {0}:{1}|chpasswd && ".format(
                    pipes.quote(i),
                    pipes.quote(password),
                )
            cmd += " /bin/true\""
            cret = __salt__['cmd.run_all'](cmd)
            if cret['retcode'] != 0:
                raise ValueError('Can\'t change passwords')
            ret['comment'] = 'Password updated for {0}'.format(users)
        except ValueError, ex:
            trace = traceback.format_exc()
            ret['result'] = False
            ret['comment'] = 'Error in setting base password\n'
            ret['comment'] += '{0}\n{1}\n'.format(ex, trace)
    else:
        ret['result'] = False
        ret['comment'] = 'No user selected'
    return ret


def update_lxc_conf(name, lxc_conf, lxc_conf_unset):
    '''Edit LXC configuration options

    CLI Example:

    .. code-block:: bash

        salt-call -lall lxc.update_lxc_conf ubuntu \
                lxc_conf="[{'network.ipv4.ip':'10.0.3.5'}]" \
                lxc_conf_unset="['lxc.utsname']"

    '''
    changes = {'edited': [], 'added': [], 'removed': []}
    ret = {'changes': changes, 'result': True, 'comment': ''}
    lxc_conf_p = '/var/lib/lxc/{0}/config'.format(name)
    if not __salt__['lxc.exists'](name):
        ret['result'] = False
        ret['comment'] = 'Container does not exist: {0}'.format(name)
    elif not os.path.exists(lxc_conf_p):
        ret['result'] = False
        ret['comment'] = (
            'Configuration does not exist: {0}'.format(lxc_conf_p))
    else:
        with open(lxc_conf_p, 'r') as fic:
            filtered_lxc_conf = []
            for row in lxc_conf:
                if not row:
                    continue
                for conf in row:
                    filtered_lxc_conf.append((conf.strip(),
                                              row[conf].strip()))
            ret['comment'] = 'lxc.conf is up to date'
            lines = []
            orig_config = fic.read()
            for line in orig_config.splitlines():
                if line.startswith('#') or not line.strip():
                    lines.append([line, ''])
                else:
                    line = line.split('=')
                    index = line.pop(0)
                    val = (index.strip(), '='.join(line).strip())
                    if not val in lines:
                        lines.append(val)
            for k, item in filtered_lxc_conf:
                matched = False
                for idx, line in enumerate(lines[:]):
                    if line[0] == k:
                        matched = True
                        lines[idx] = (k, item)
                        if '='.join(line[1:]).strip() != item.strip():
                            changes['edited'].append(
                                ({line[0]: line[1:]}, {k: item}))
                            break
                if not matched:
                    if not (k, item) in lines:
                        lines.append((k, item))
                    changes['added'].append({k: item})
            dest_lxc_conf = []
            # filter unset
            if lxc_conf_unset:
                for line in lines:
                    for opt in lxc_conf_unset:
                        if (
                            not line[0].startswith(opt)
                            and not line in dest_lxc_conf
                        ):
                            dest_lxc_conf.append(line)
                        else:
                            changes['removed'].append(opt)
            else:
                dest_lxc_conf = lines
            conf = ''
            for k, val in dest_lxc_conf:
                if not val:
                    conf += '{0}\n'.format(k)
                else:
                    conf += '{0} = {1}\n'.format(k.strip(), val.strip())
            conf_changed = conf != orig_config
            chrono = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            if conf_changed:
                wfic = open('{0}.{1}'.format(lxc_conf_p, chrono), 'w')
                wfic.write(conf)
                wfic.close()
                wfic = open(lxc_conf_p, 'w')
                wfic.write(conf)
                wfic.close()
                ret['comment'] = 'Updated'
                ret['result'] = True
    if (
        not changes['added']
        and not changes['edited']
        and not changes['removed']
    ):
        ret['changes'] = {}
    return ret


def set_dns(name, dnsservers=None, searchdomains=None):
    '''Update container DNS configuration
    and possibly also resolvonf one.

    CLI Example:

    .. code-block:: bash

        salt-call -lall lxc.set_dns ubuntu ['8.8.8.8', '4.4.4.4']

    '''
    ret = {'result': False}
    if not dnsservers:
        dnsservers = ['8.8.8.8', '4.4.4.4']
    if not searchdomains:
        searchdomains = []
    dns = ['nameserver {0}'.format(d) for d in dnsservers]
    dns.extend(['search {0}'.format(d) for d in searchdomains])
    dns = "\n".join(dns)
    has_resolvconf = not int(
        __salt__['cmd.run'](('lxc-attach -n \'{0}\' -- '
                             '/usr/bin/test -e /etc/resolvconf/resolv.conf.d/base;'
                             'echo ${{?}}').format(name)))
    if has_resolvconf:
        cret = __salt__['cmd.run_all']((
            'lxc-attach -n \'{0}\' -- '
            'rm /etc/resolvconf/resolv.conf.d/base &&'
            'echo \'{1}\'|lxc-attach -n \'{0}\' -- '
            'tee /etc/resolvconf/resolv.conf.d/base'
        ).format(name, dns))
        if not cret['retcode']:
            ret['result'] = True
    cret = __salt__['cmd.run_all']((
        'lxc-attach -n \'{0}\' -- rm /etc/resolv.conf &&'
        'echo \'{1}\'|lxc-attach -n \'{0}\' -- '
        'tee /etc/resolv.conf'
    ).format(name, dns))
    if not cret['retcode']:
        ret['result'] = True
    return ret


def bootstrap(name, config=None, approve_key=True, install=True):
    '''
    Install and configure salt in a container.

    .. code-block:: bash

        salt 'minion' lxc.bootstrap name [config=config_data] \\
                [approve_key=(True|False)] [install=(True|False)]

    config
        Minion configuration options. By default, the ``master`` option is set
        to the target host's master.

    approve_key
        Request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host. Default: ``True``

    install
        Whether to attempt a full installation of salt-minion if needed.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.bootstrap ubuntu
    '''

    infos = __salt__['lxc.info'](name)
    if not infos:
        return None

    prior_state = _ensure_running(name)
    if not prior_state:
        return prior_state

    cmd = 'bash -c "if type salt-minion; then ' \
          'salt-call --local service.stop salt-minion; exit 0; ' \
          'else exit 1; fi"'
    needs_install = bool(__salt__['lxc.run_cmd'](name, cmd, stdout=False))

    tmp = tempfile.mkdtemp()
    cfg_files = __salt__['seed.mkconfig'](config, tmp=tmp, id_=name,
                                          approve_key=approve_key)

    if needs_install:
        if install:
            bs_ = __salt__['config.gather_bootstrap_script']()
            cp(name, bs_, '/tmp/bootstrap.sh')
            cp(name, cfg_files['config'], '/tmp/')
            cp(name, cfg_files['privkey'], '/tmp/')
            cp(name, cfg_files['pubkey'], '/tmp/')

            cmd = 'sh /tmp/bootstrap.sh -c /tmp'
            res = not __salt__['lxc.run_cmd'](name, cmd, stdout=False)
        else:
            res = False
    else:
        minion_config = salt.config.minion_config(cfg_files['config'])
        pki_dir = os.path.join(minion_config['pki_dir'], 'minion')
        cp(name, cfg_files['config'], '/etc/salt/minion')
        cp(name, cfg_files['privkey'], pki_dir)
        cp(name, cfg_files['pubkey'], pki_dir)
        run_cmd(name, 'salt-call --local service.start salt-minion',
                stdout=False)
        res = True

    shutil.rmtree(tmp)
    if prior_state == 'stopped':
        __salt__['lxc.stop'](name)
    elif prior_state == 'frozen':
        __salt__['lxc.freeze'](name)
    return res


def run_cmd(name, cmd, no_start=False, preserve_state=True,
            stdout=True, stderr=False):
    '''
    Run a command inside the container.

    CLI Example:

    .. code-block:: bash

        salt 'minion' name command [no_start=(True|False)] \\
                [preserve_state=(True|False)] [stdout=(True|False)] \\
                [stderr=(True|False)]

    name
        Name of the container on which to operate.

    cmd
        Command to run

    no_start
        If the container is not running, don't start it. Default: ``False``

    preserve_state
        After running the command, return the container to its previous
        state. Default: ``True``

    stdout:
        Return stdout. Default: ``True``

    stderr:
        Return stderr. Default: ``False``

    .. note::

        If stderr and stdout are both ``False``, the return code is returned.
        If stderr and stdout are both ``True``, the pid and return code are
        also returned.
    '''
    prior_state = _ensure_running(name, no_start=no_start)
    if not prior_state:
        return prior_state
    res = __salt__['cmd.run_all'](
            'lxc-attach -n \'{0}\' -- {1}'.format(name, cmd))

    if preserve_state:
        if prior_state == 'stopped':
            __salt__['lxc.stop'](name)
        elif prior_state == 'frozen':
            __salt__['lxc.freeze'](name)

    if stdout and stderr:
        return res
    elif stdout:
        return res['stdout']
    elif stderr:
        return res['stderr']
    else:
        return res['retcode']


def cp(name, src, dest):
    '''
    Copy a file or directory from the host into a container

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.cp /tmp/foo /root/
    '''

    if state(name) != 'running':
        return {'error': 'container is not running'}
    if not os.path.exists(src):
        return {'error': 'src does not exist'}
    if not os.path.isfile(src):
        return {'error': 'src must be a regular file'}
    src_dir, src_name = os.path.split(src)

    dest_dir, dest_name = os.path.split(dest)
    if run_cmd(name, 'test -d {0}'.format(dest_dir), stdout=False):
        return {'error': '{0} is not a directory on the container'.format(dest_dir)}
    if not dest_name:
        dest_name = src_name

    cmd = 'cat {0} | lxc-attach -n {1} -- tee {2} > /dev/null'.format(
            src, name, os.path.join(dest_dir, dest_name))
    log.info(cmd)
    ret = __salt__['cmd.run_all'](cmd)
    return ret
