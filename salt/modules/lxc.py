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
import re

#import salt libs
import salt.utils
#import subprocess
import salt.utils.cloud

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list'
}


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
    '''
    To speed up the whole thing, we decided to not use the
    subshell way and assume things are in place for lxc
    Discussion made by @kiorky and @thatch45
    if salt.utils.which('lxc-autostart'):
        return 'lxc'
    elif salt.utils.which('lxc-version'):
        passed = False
        try:
            passed = subprocess.check_output(
                'lxc-version').split(':')[1].strip() >= '1.0'
        except Exception:
            pass
        if not passed:
            log.warning('Support for lxc < 1.0 may be incomplete.')
        return 'lxc'
    return False
    '''
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
        cmd += ' -B {0}'.format(backing)
        if lvname:
            cmd += ' --lvname {0}'.format(vgname)
        if vgname:
            cmd += ' --vgname {0}'.format(vgname)
        if fstype:
            cmd += ' --fstype {0}'.format(size)
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

    .. code-block:: bash

        salt 'minion' lxc.clone name ARGS

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

    .. code-block:: bash

        salt '*' lxc.clone myclone ubuntu "snapshot=True"

    '''

    if exists(name):
        return {'created': False, 'error': 'container already exists'}
    if not exists(orig):
        return {'created': False,
                'error': 'original container does not exists'.format(orig)}
    if not snapshot:
        snapshot = ''
    else:
        snapshot = '-s'
    cmd = 'lxc-clone {2} -o {0} -n {1}'.format(orig, name, snapshot)
    profile = _lxc_profile(profile)

    def select(k, default=None):
        kw = kwargs.pop(k, None)
        p = profile.pop(k, default)
        return kw or p

    vgname = select('vgname')
    size = select('size', '1G')
    if size:
        cmd += ' -L {0}'.format(size)
    if vgname:
        cmd += ' -v {0}'.format(vgname)

    ret = __salt__['cmd.run_all'](cmd)
    if ret['retcode'] == 0 and exists(name):
        return {'cloned': True}
    else:
        if exists(name):
            # destroy the container if it was partially created
            cmd = 'lxc-destroy -n {0}'.format(name)
            __salt__['cmd.retcode'](cmd)
        log.warn('lxc-clone failed to create container')
        return {'created': False, 'error':
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


def start(name, restart=False):
    '''
    Start the named container.

    .. code-block:: bash

        salt '*' lxc.start name
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Started'}
    try:
        exists = __salt__['lxc.exists'](name)
        if not exists:
            return {'name': name,
                    'result': False,
                    'comment': 'Container does not exists'}
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

    .. code-block:: bash

        salt '*' lxc.stop name
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'Stopped'}
    try:
        exists = __salt__['lxc.exists'](name)
        if not exists:
            return {'name': name,
                    'result': False,
                    'changes': {},
                    'comment': 'Container does not exists'}
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
    return name in l['running'] + l['stopped'] + l['frozen']


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


def templates():
    '''
    Returns a list of existing templates

    .. code-block:: bash

        salt '*' lxc.templates
    '''
    templates = []
    san = re.compile('^lxc-')
    tdir = '/usr/share/lxc/templates'
    if os.path.isdir(tdir):
        templates.extend(
            [san.sub('', a) for a in os.listdir(tdir)]
        )
    templates.sort()
    return templates


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
                raise Exception('Can\'t change passwords')
            ret['comment'] = 'Password updated for {0}'.format(users)
        except Exception, ex:
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
        ret['comment'] = 'Container does not exists: {0}'.fomart(name)
    elif not os.path.exists(lxc_conf_p):
        ret['result'] = False
        ret['comment'] = (
            'Configuration does not exists: {0}'.format(lxc_conf_p))
    else:
        try:
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
        except Exception, ex:
            trace = traceback.format_exc()
            ret['result'] = False
            ret['comment'] = 'Error in storing lxc configuration'
            ret['comment'] += '{0}\n{1}\n'.format(ex, trace)
    if (
        not changes['added']
        and not changes['edited']
        and not changes['removed']
    ):
        ret['changes'] = {}
    return ret


def set_dns(name, dnsservers=None, searchdomains=None):
    '''Update container dns configuration
    and possibly also resolvonf one.

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

#
