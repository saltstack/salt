# -*- coding: utf-8 -*-
'''
Control Linux Containers via Salt

:depends: lxc package for distribution

lxc >= 1.0 (even beta alpha) is required

'''

from __future__ import absolute_import

# Import python libs
from __future__ import print_function
import traceback
import datetime
import pipes
import copy
import logging
import tempfile
import os
import time
import shutil
import re
import random
import salt.ext.six as six
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse  # pylint: disable=E0611

# Import salt libs
import salt
import salt.utils.odict
import salt.utils
import salt.utils.dictupdate
import salt.utils.network
from salt.utils import vt
from salt.exceptions import CommandExecutionError, SaltInvocationError
import salt.utils.cloud
import salt.config

# Set up logging
log = logging.getLogger(__name__)

# Don't shadow built-in's.
__func_alias__ = {
    'list_': 'list',
    'ls_': 'ls'
}


ATTACH_PREFIX = (
    'lxc-attach --clear-env --set-var '
    'PATH=/bin:/usr/bin:/sbin:/usr/sbin:/opt/bin:'
    '/usr/local/bin:/usr/local/sbin -n {0} -- '
)
DEFAULT_NIC_PROFILE = {'eth0': {'link': 'br0', 'type': 'veth'}}
SEED_MARKER = '/lxc.initial_seed'
_marker = object()


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


def cloud_init_interface(name, vm_=None, **kwargs):
    '''
    Interface between salt.cloud.lxc driver and lxc.init
    ``vm_`` is a mapping of vm opts in the salt.cloud format
    as documented for the lxc driver.

    This can be used either:

    - from the salt cloud driver
    - because you find the argument to give easier here
      than using directly lxc.init

    .. warning::
        BE REALLY CAREFUL CHANGING DEFAULTS !!!
        IT'S A RETRO COMPATIBLE INTERFACE WITH
        THE SALT CLOUD DRIVER (ask kiorky).

    name
        name of the lxc container to create
    from_container
        which container we use as a template
        when running lxc.clone
    image
        which template do we use when we
        are using lxc.create. This is the default
        mode unless you specify something in from_container
    backing
        which backing store to use.
        Values can be: overlayfs, dir(default), lvm, zfs, brtfs
    fstype
        When using a blockdevice level backing store,
        which filesystem to use on
    size
        When using a blockdevice level backing store,
        which size for the filesystem to use on
    snapshot
        Use snapshot when cloning the container source
    vgname
        if using LVM: vgname
    lgname
        if using LVM: lvname
    pub_key
        public key to preseed the minion with.
        Can be the keycontent or a filepath
    priv_key
        private key to preseed the minion with.
        Can be the keycontent or a filepath
    ip
        ip for the primary nic
    mac
        mac for the primary nic
    netmask
        netmask for the primary nic (24)
        = ``vm_.get('netmask', '24')``
    bridge
        bridge for the primary nic (lxcbr0)
    gateway
        network gateway for the container
    additional_ips
        additional ips which will be wired on the main bridge (br0)
        which is connected to internet.
        Be aware that you may use manual virtual mac addresses
        provided by you provider (online, ovh, etc).
        This is a list of mappings ``{ip: '', mac: '',netmask:''}``
        Set gateway to ``None`` and an interface with a gateway
        to escape from another interface that's eth0.
        e.g.:

        .. code-block:: python

            {'mac': '00:16:3e:01:29:40',
             'gateway': None, #default
             'link': 'br0', #default
             'netmask': '', #default
             'ip': '22.1.4.25'}

    unconditional_install
        given to lxc.bootstrap (see relative doc)
    force_install
        given to lxc.bootstrap (see relative doc)
    config
        any extra argument for the salt minion config
    dnsservers
        dns servers to set inside the container
    autostart
        autostart the container at boot time
    password
        administrative password for the container
    users
        administrative users for the container
        default: [root] and [root, ubuntu] on ubuntu

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.cloud_init_interface foo

    '''
    if vm_ is None:
        vm_ = {}
    vm_ = copy.deepcopy(vm_)
    vm_ = salt.utils.dictupdate.update(vm_, kwargs)
    profile = _lxc_profile(vm_.get('profile', {}))
    if name is None:
        name = vm_['name']
    from_container = vm_.get('from_container', None)
    # if we are on ubuntu, default to ubuntu
    default_template = ''
    if __grains__.get('os', '') in ['Ubuntu']:
        default_template = 'ubuntu'
    image = vm_.get('image', profile.get('template',
                                         default_template))
    vgname = vm_.get('vgname', None)
    backing = vm_.get('backing', 'dir')
    snapshot = vm_.get('snapshot', False)
    autostart = bool(vm_.get('autostart', True))
    dnsservers = vm_.get('dnsservers', [])
    if not dnsservers:
        dnsservers = ['8.8.8.8', '4.4.4.4']
    password = vm_.get('password', 's3cr3t')
    fstype = vm_.get('fstype', None)
    lvname = vm_.get('lvname', None)
    pub_key = vm_.get('pub_key', None)
    priv_key = vm_.get('priv_key', None)
    size = vm_.get('size', '20G')
    script = vm_.get('script', None)
    script_args = vm_.get('script_args', None)
    if image:
        profile['template'] = image
    if vgname:
        profile['vgname'] = vgname
    if backing:
        profile['backing'] = backing
    users = vm_.get('users', None)
    if users is None:
        users = []
    ssh_username = vm_.get('ssh_username', None)
    if ssh_username and (ssh_username not in users):
        users.append(ssh_username)
    ip = vm_.get('ip', None)
    mac = vm_.get('mac', None)
    netmask = vm_.get('netmask', '24')
    bridge = vm_.get('bridge', 'lxcbr0')
    gateway = vm_.get('gateway', 'auto')
    unconditional_install = vm_.get('unconditional_install', False)
    force_install = vm_.get('force_install', True)
    config = vm_.get('config', {})
    if not config:
        config = vm_.get('minion', {})
    if not config:
        config = {}
    config.setdefault('master',
                      vm_.get('master',
                              __opts__.get('master',
                                           __opts__['id'])))
    config.setdefault(
        'master_port',
        vm_.get('master_port',
                __opts__.get('master_port',
                             __opts__.get('ret_port',
                                          __opts__.get('4506')))))
    if not config['master']:
        config = {}
    eth0 = {}
    nic_opts = {'eth0': eth0}
    bridge = vm_.get('bridge', 'lxcbr0')
    if ip is None:
        nic_opts = None
    else:
        fullip = ip
        if netmask:
            fullip += '/{0}'.format(netmask)
        eth0['ipv4'] = fullip
        if mac is not None:
            eth0['hwaddr'] = mac
        if bridge:
            eth0['link'] = bridge
    for ix, iopts in enumerate(vm_.get("additional_ips", [])):
        ifh = "eth{0}".format(ix+1)
        ethx = nic_opts.setdefault(ifh, {})
        gw = iopts.get('gateway', None)
        if gw:
            ethx['gateway'] = gw
            vm_['gateway'] = gateway = None
        ethx['link'] = iopts.get('link', 'br0')
        ethx['ipv4'] = iopts['ip']
        nm = iopts.get('netmask', '')
        if nm:
            ethx['ipv4'] += '/{0}'.format(nm)
        for i in ['mac', 'hwaddr']:
            if i in iopts:
                ethx['hwaddr'] = iopts[i]
        if 'hwaddr' not in ethx:
            raise ValueError('No mac for {0}'.format(ifh))
    gateway = vm_.get('gateway', 'auto')
    #
    lxc_init_interface = {}
    lxc_init_interface['name'] = name
    lxc_init_interface['config'] = config
    lxc_init_interface['memory'] = 0  # nolimit
    lxc_init_interface['pub_key'] = pub_key
    lxc_init_interface['priv_key'] = priv_key
    lxc_init_interface['bridge'] = bridge
    lxc_init_interface['gateway'] = gateway
    lxc_init_interface['nic_opts'] = nic_opts
    lxc_init_interface['clone'] = from_container
    lxc_init_interface['profile'] = profile
    lxc_init_interface['snapshot'] = snapshot
    lxc_init_interface['dnsservers'] = dnsservers
    lxc_init_interface['fstype'] = fstype
    lxc_init_interface['vgname'] = vgname
    lxc_init_interface['size'] = size
    lxc_init_interface['lvname'] = lvname
    lxc_init_interface['force_install'] = force_install
    lxc_init_interface['unconditional_install'] = (
        unconditional_install
    )
    lxc_init_interface['bootstrap_url'] = script
    lxc_init_interface['bootstrap_args'] = script_args
    lxc_init_interface['bootstrap_shell'] = 'sh'
    lxc_init_interface['autostart'] = autostart
    lxc_init_interface['users'] = users
    lxc_init_interface['password'] = password
    return lxc_init_interface


def get_profile(name=None, **kwargs):
    '''
    .. versionadded:: Lithium

    Gather a pre-configured set of LXC configuration parameters. If no
    arguments are passed, an empty profile is returned.

    Profiles can be defined in the minion or master config files, or in pillar
    or grains, and are loaded using :mod:`config.get
    <salt.modules.config.get>`. The key under which LXC profiles must be
    configured is ``lxc.profile``. An example LXC profile would be as follows:

    .. code-block:: yaml

        lxc.profile:
          ubuntu:
            template: ubuntu
            backing: lvm
            vgname: lxc
            size: 1G

    Parameters set in a profile can be overridden by passing additional
    arguments to this function.

    CLI Example::

    .. code-block:: bash

        salt-call lxc.profile centos
        salt-call lxc.profile ubuntu template=ubuntu backing=overlayfs
    '''
    profilename = name if name is not None else 'no_profile'
    key = 'lxc.profile.{0}'.format(profilename)
    try:
        return __context__[key]
    except KeyError:
        default_profile = \
            __salt__['config.get']('lxc.profile', {}).get(name, {}) \
            if name is not None \
            else {}
        # save the resulting profile in the context
        rprofile = salt.utils.dictupdate.update(
            copy.deepcopy(default_profile),
            kwargs
        )
        __context__[key] = rprofile
    return __context__[key]


def _rand_cpu_str(cpu):
    '''
    Return a random subset of cpus for the cpuset config
    '''
    cpu = int(cpu)
    avail = __salt__['status.nproc']()
    if cpu < avail:
        return '0-{0}'.format(avail)
    to_set = set()
    while len(to_set) < cpu:
        choice = random.randint(0, avail - 1)
        if choice not in to_set:
            to_set.add(str(choice))
    return ','.join(sorted(to_set))


def _get_network_conf(conf_tuples=None, **kwargs):
    nic = kwargs.pop('nic', None)
    ret = []
    if not nic:
        return ret
    kwargs = copy.deepcopy(kwargs)
    gateway = kwargs.pop('gateway', None)
    bridge = kwargs.get('bridge', None)
    if not conf_tuples:
        conf_tuples = []

    if nic:
        nicp = __salt__['config.get']('lxc.nic', {}).get(
            nic, DEFAULT_NIC_PROFILE)
        nic_opts = kwargs.pop('nic_opts', {})
        if nic_opts:
            for dev, args in nic_opts.items():
                ethx = nicp.setdefault(dev, {})
                ethx = salt.utils.dictupdate.update(ethx, args)
        ifs = [a for a in nicp]
        ifs.sort()
        gateway_set = False
        for dev in ifs:
            args = nicp[dev]
            ret.append({'lxc.network.type': args.pop('type', '')})
            ret.append({'lxc.network.name': dev})
            ret.append({'lxc.network.flags': args.pop('flags', 'up')})
            opts = nic_opts.get(dev) if nic_opts else {}
            mac = opts.get('mac', '')
            if opts:
                ipv4 = opts.get('ipv4')
                ipv6 = opts.get('ipv6')
            else:
                ipv4, ipv6 = None, None
                if not mac:
                    mac = salt.utils.gen_mac()
            if mac:
                ret.append({'lxc.network.hwaddr': mac})
            if ipv4:
                ret.append({'lxc.network.ipv4': ipv4})
            if ipv6:
                ret.append({'lxc.network.ipv6': ipv6})
            for k, v in args.items():
                if k == 'link' and bridge:
                    v = bridge
                v = opts.get(k, v)
                if k in ['gateway', 'mac']:
                    continue
                ret.append({'lxc.network.{0}'.format(k): v})
            # gateway (in automode) must be appended following network conf !
            if not gateway:
                gateway = args.get('gateway', None)
            if gateway is not None and not gateway_set:
                ret.append({'lxc.network.ipv4.gateway': gateway})
                # only one network gateway ;)
                gateway_set = True
        # normally, this wont happen
        # set the gateway if specified even if we did
        # not managed the network underlying
        if gateway is not None and not gateway_set:
            ret.append({'lxc.network.ipv4.gateway': gateway})
            # only one network gateway ;)
            gateway_set = True

    old = _get_veths(conf_tuples)
    new = _get_veths(ret)
    # verify that we did not loose the mac settings
    for iface in [a for a in new]:
        ndata = new[iface]
        nmac = ndata.get('lxc.network.hwaddr', '')
        ntype = ndata.get('lxc.network.type', '')
        omac, otype = '', ''
        if iface in old:
            odata = old[iface]
            omac = odata.get('lxc.network.hwaddr', '')
            otype = odata.get('lxc.network.type', '')
        # default for network type is setted here
        # attention not to change the network type
        # without a good and explicit reason to.
        if otype and not ntype:
            ntype = otype
        if not ntype:
            ntype = 'veth'
        new[iface]['lxc.network.type'] = ntype
        if omac and not nmac:
            new[iface]['lxc.network.hwaddr'] = omac

    ret = []
    for v in new.values():
        for row in v:
            ret.append({row: v[row]})
    return ret


def _get_memory(memory):
    '''
    Handle the saltcloud driver and lxc runner memory restriction
    differences.
    Runner limits to 1024MB by default
    SaltCloud does not restrict memory usage by default
    '''
    if memory is None:
        memory = 1024
    if memory:
        memory = memory * 1024 * 1024
    return memory


def _get_autostart(autostart):
    if autostart is None:
        autostart = True
    if autostart:
        autostart = '1'
    else:
        autostart = '0'
    return autostart


def _get_lxc_default_data(**kwargs):
    kwargs = copy.deepcopy(kwargs)
    ret = {}
    autostart = _get_autostart(kwargs.pop('autostart', None))
    ret['lxc.start.auto'] = autostart
    memory = _get_memory(kwargs.pop('memory', None))
    if memory:
        ret['lxc.cgroup.memory.limit_in_bytes'] = memory
    cpuset = kwargs.pop('cpuset', None)
    if cpuset:
        ret['lxc.cgroup.cpuset.cpus'] = cpuset
    cpushare = kwargs.pop('cpushare', None)
    cpu = kwargs.pop('cpu', None)
    if cpushare:
        ret['lxc.cgroup.cpu.shares'] = cpushare
    if cpu and not cpuset:
        ret['lxc.cgroup.cpuset.cpus'] = _rand_cpu_str(cpu)
    return ret


def _config_list(conf_tuples=None, **kwargs):
    '''
    Return a list of dicts from the salt level configurations
    '''
    if not conf_tuples:
        conf_tuples = []
    kwargs = copy.deepcopy(kwargs)
    ret = []
    default_data = _get_lxc_default_data(**kwargs)
    for k, val in default_data.items():
        ret.append({k: val})
    net_datas = _get_network_conf(conf_tuples=conf_tuples, **kwargs)
    ret.extend(net_datas)
    return ret


def _get_veths(net_data):
    '''Parse the nic setup inside lxc conf tuples back
    to a dictionary indexed by network interface'''
    if isinstance(net_data, dict):
        net_data = list(net_data.items())
    nics = salt.utils.odict.OrderedDict()
    current_nic = salt.utils.odict.OrderedDict()
    for item in net_data:
        if item and isinstance(item, dict):
            item = list(item.items())[0]
        if item[0] == 'lxc.network.type':
            current_nic = salt.utils.odict.OrderedDict()
        if item[0] == 'lxc.network.name':
            nics[item[1].strip()] = current_nic
        current_nic[item[0].strip()] = item[1].strip()
    return nics


class _LXCConfig(object):
    '''
    LXC configuration data
    '''
    pattern = re.compile(r'^(\S+)(\s*)(=)(\s*)(.*)')
    non_interpretable_pattern = re.compile(r'^((#.*)|(\s*))$')

    def __init__(self, **kwargs):
        kwargs = copy.deepcopy(kwargs)
        self.name = kwargs.pop('name', None)
        self.data = []
        if self.name:
            self.path = '/var/lib/lxc/{0}/config'.format(self.name)
            if os.path.isfile(self.path):
                with salt.utils.fopen(self.path) as f:
                    for l in f.readlines():
                        match = self.pattern.findall((l.strip()))
                        if match:
                            self.data.append((match[0][0], match[0][-1]))
                        match = self.non_interpretable_pattern.findall(
                            (l.strip()))
                        if match:
                            self.data.append(('', match[0][0]))
        else:
            self.path = None

        def _replace(k, v):
            if v:
                self._filter_data(k)
                self.data.append((k, v))

        default_data = _get_lxc_default_data(**kwargs)
        for k, val in default_data.items():
            _replace(k, val)
        old_net = self._filter_data('lxc.network')
        net_datas = _get_network_conf(conf_tuples=old_net, **kwargs)
        if net_datas:
            for row in net_datas:
                self.data.extend(list(row.items()))

        # be sure to reset harmful settings
        for i in ['lxc.cgroup.memory.limit_in_bytes']:
            if not default_data.get(i):
                self._filter_data(i)

    def as_string(self):
        chunks = ('{0[0]}{1}{0[1]}'.format(item, (' = ' if item[0] else '')) for item in self.data)
        return '\n'.join(chunks) + '\n'

    def write(self):
        if self.path:
            content = self.as_string()
            # 2 step rendering to be sure not to open/wipe the config
            # before as_string succeeds.
            with salt.utils.fopen(self.path, 'w') as fic:
                fic.write(content)
                fic.flush()

    def tempfile(self):
        # this might look like the function name is shadowing the
        # module, but it's not since the method belongs to the class
        f = tempfile.NamedTemporaryFile()
        f.write(self.as_string())
        f.flush()
        return f

    def _filter_data(self, pat):
        removed = []
        x = []
        for i in self.data:
            if not re.match('^' + pat, i[0]):
                x.append(i)
            else:
                removed.append(i)
        self.data = x
        return removed


def get_base(**kwargs):
    '''
    If the needed base does not exist, then create it, if it does exist
    create nothing and return the name of the base lxc container so
    it can be cloned.

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.init name [cpuset=cgroups_cpuset] \\
                [nic=nic_profile] [profile=lxc_profile] \\
                [nic_opts=nic_opts] [image=network image path]\\
                [seed=(True|False)] [install=(True|False)] \\
                [config=minion_config]
    '''
    cntrs = ls_()
    if kwargs.get('image'):
        image = kwargs.get('image')
        proto = _urlparse(image).scheme
        img_tar = __salt__['cp.cache_file'](image)
        img_name = os.path.basename(img_tar)
        hash_ = salt.utils.get_hash(
                img_tar,
                __salt__['config.get']('hash_type'))
        name = '__base_{0}_{1}_{2}'.format(proto, img_name, hash_)
        if name not in cntrs:
            create(name, **kwargs)
            if kwargs.get('vgname'):
                rootfs = os.path.join('/dev', kwargs['vgname'], name)
                lxc_info = info(name)
                edit_conf(lxc_info['config'], **{'lxc.rootfs': rootfs})
        return name
    elif kwargs.get('template'):
        name = '__base_{0}'.format(kwargs['template'])
        if name not in cntrs:
            create(name, **kwargs)
            if kwargs.get('vgname'):
                rootfs = os.path.join('/dev', kwargs['vgname'], name)
                lxc_info = info(name)
                edit_conf(lxc_info['config'], **{'lxc.rootfs': rootfs})
        return name
    return ''


def init(name,
         cpuset=None,
         cpushare=None,
         memory=None,
         nic='default',
         profile=None,
         nic_opts=None,
         cpu=None,
         autostart=True,
         password=None,
         users=None,
         dnsservers=None,
         bridge=None,
         gateway=None,
         pub_key=None,
         priv_key=None,
         force_install=False,
         unconditional_install=False,
         bootstrap_args=None,
         bootstrap_shell=None,
         bootstrap_url=None,
         **kwargs):
    '''
    Initialize a new container.

    This is a partial idempotent function as if it is already
    provisioned, we will reset a bit the lxc configuration
    file but much of the hard work will be escaped as
    markers will prevent re-execution of harmful tasks.

    name
        Name of the container.
    cpus
        Select a random number of cpu cores and assign it to the cpuset, if the
        cpuset option is set then this option will be ignored
    cpuset
        Explicitly define the cpus this container will be bound to
    cpushare
        cgroups cpu shares.
    autostart
        autostart container on reboot
    memory
        cgroups memory limit, in MB.
        (0 for nolimit, None for old default 1024MB)
    gateway
        the ipv4 gateway to use
        the default does nothing more than lxcutils does
    bridge
        the bridge to use
        the default does nothing more than lxcutils does
    nic
        Network interfaces profile (defined in config or pillar).
    users
        Sysadmins users to set the administrative password to
        e.g. [root, ubuntu, sysadmin], default [root] and [root, ubuntu]
        on ubuntu
    password
        Set the initial password for default sysadmin users, at least root
        but also can be used for sudoers, e.g. [root, ubuntu, sysadmin]
    profile
        A LXC profile (defined in config or pillar).
        This can be either a real profile mapping or a string
        to retrieve it in configuration
    nic_opts
        Extra options for network interfaces. E.g.:

        .. code-block:: bash

            {"eth0": {"mac": "aa:bb:cc:dd:ee:ff", "ipv4": "10.1.1.1", "ipv6": "2001:db8::ff00:42:8329"}}

        or

        .. code-block:: bash

            {"eth0": {"mac": "aa:bb:cc:dd:ee:ff", "ipv4": "10.1.1.1/24", "ipv6": "2001:db8::ff00:42:8329"}}
    start
        Start the newly created container.
    dnsservers
        list of dns servers to set in the container, default [] (no setting)
    seed
        Seed the container with the minion config. Default: ``True``
    install
        If salt-minion is not already installed, install it. Default: ``True``
    config
        Optional config parameters. By default, the id is set to
        the name of the container.
    pub_key
        Explicit public key to preseed the minion with (optional).
        This can be either a filepath or a string representing the key
    priv_key
        Explicit private key to preseed the minion with (optional).
        This can be either a filepath or a string representing the key
    approve_key
        If explicit preseeding is not used;
        Attempt to request key approval from the master. Default: ``True``
    clone
        Original from which to use a clone operation to create the container.
        Default: ``None``
    bootstrap_url
        See lxc.bootstrap
    bootstrap_shell
        See lxc.bootstrap
    bootstrap_args
        See lxc.bootstrap
    force_install
        Force installation even if salt-minion is detected,
        this is the way to run vendor bootstrap scripts even
        if a salt minion is already present in the container
    unconditional_install
        Run the script even if the container seems seeded

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.init name [cpuset=cgroups_cpuset] \\
                [cpushare=cgroups_cpushare] [memory=cgroups_memory] \\
                [nic=nic_profile] [profile=lxc_profile] \\
                [nic_opts=nic_opts] [start=(True|False)] \\
                [seed=(True|False)] [install=(True|False)] \\
                [config=minion_config] [approve_key=(True|False) \\
                [clone=original] [autostart=True] \\
                [priv_key=/path_or_content] [pub_key=/path_or_content] \\
                [bridge=lxcbr0] [gateway=10.0.3.1] \\
                [dnsservers[dns1,dns2]] \\
                [users=[foo]] password='secret'

    '''
    kwargs = copy.deepcopy(kwargs)
    comment = ''
    ret = {'error': '', 'name': name, 'result': True}
    changes = ret.setdefault('changes', {})
    if users is None:
        users = []
    dusers = ['root']
    if (
        __grains__['os'] in ['Ubuntu']
        and 'ubuntu' not in users
    ):
        dusers.append('ubuntu')
    for user in dusers:
        if user not in users:
            users.append(user)
    if not isinstance(profile, dict):
        profile = _lxc_profile(profile)
    profile = copy.deepcopy(profile)

    def select(k, default=None):
        kw = kwargs.pop(k, _marker)
        p = profile.pop(k, default)
        # let kwargs be really be the preferred choice
        if kw is _marker:
            kw = p
        return kw

    tvg = select('vgname')
    vgname = tvg if tvg else __salt__['config.get']('lxc.vgname')
    start_ = select('start', True)
    ret['started'] = start_
    autostart = select('autostart', autostart)
    seed = select('seed', True)
    install = select('install', True)
    seed_cmd = select('seed_cmd')
    salt_config = select('config')
    approve_key = select('approve_key', True)
    clone_from = select('clone')

    # If using a volume group then set up to make snapshot cow clones
    if vgname and not clone_from:
        clone_from = get_base(vgname=vgname, **kwargs)
        if not kwargs.get('snapshot') is False:
            kwargs['snapshot'] = True
    does_exist = exists(name)
    to_reboot = False
    remove_seed_marker = False
    if does_exist:
        comment += 'Container already exists\n'
    elif clone_from:
        remove_seed_marker = True
        ret.update(
            clone(name, clone_from,
                                  profile=profile, **kwargs))
        if not ret.get('cloned', False):
            return ret
        cfg = _LXCConfig(name=name, nic=nic, nic_opts=nic_opts,
                         bridge=bridge, gateway=gateway,
                         autostart=autostart,
                         cpuset=cpuset, cpushare=cpushare, memory=memory)
        old_chunks = read_conf(cfg.path)
        cfg.write()
        chunks = read_conf(cfg.path)
        if old_chunks != chunks:
            to_reboot = True
    else:
        remove_seed_marker = True
        cfg = _LXCConfig(nic=nic, nic_opts=nic_opts, cpuset=cpuset,
                         bridge=bridge, gateway=gateway,
                         autostart=autostart,
                         cpushare=cpushare, memory=memory)
        with cfg.tempfile() as cfile:
            ret.update(
                create(name, config=cfile.name,
                                       profile=profile, **kwargs))
        if not ret.get('created', False):
            return ret
        path = '/var/lib/lxc/{0}/config'.format(name)
        old_chunks = []
        if os.path.exists(path):
            old_chunks = read_conf(path)
        for comp in _config_list(conf_tuples=old_chunks,
                                 cpu=cpu,
                                 nic=nic, nic_opts=nic_opts, bridge=bridge,
                                 cpuset=cpuset, cpushare=cpushare,
                                 memory=memory):
            edit_conf(path, **comp)
        chunks = read_conf(path)
        if old_chunks != chunks:
            to_reboot = True
    if remove_seed_marker:
        lxcret = run_cmd(
            name, 'rm -f \"{0}\"'.format(SEED_MARKER),
            stdout=False, stderr=False)

    # last time to be sure any of our property is correctly applied
    cfg = _LXCConfig(name=name, nic=nic, nic_opts=nic_opts,
                     bridge=bridge, gateway=gateway,
                     autostart=autostart,
                     cpuset=cpuset, cpushare=cpushare, memory=memory)
    old_chunks = []
    if os.path.exists(cfg.path):
        old_chunks = read_conf(cfg.path)
    cfg.write()
    chunks = read_conf(cfg.path)
    if old_chunks != chunks:
        comment += 'Container configuration updated\n'
        to_reboot = True
    else:
        if not to_reboot:
            comment += 'Container already correct\n'
    if to_reboot:
        stop(name)
    if clone_from:
        inner = 'cloned'
        comment += 'Container cloned\n'
    else:
        inner = 'created'
        comment += 'Container created\n'
    ret[inner] = True
    if (
        not does_exist
        or (
            does_exist
            and state(name) != 'running'
        )
    ):
        ret['state'] = start(name)
    ret['state'] = state(name)

    # set the default user/password, only the first time
    if password:
        changes['250_password'] = 'Passwords in place\n'
        gid = '/.lxc.initial_pass'
        gids = [gid,
                '/lxc.initial_pass',
                '/.lxc.{0}.initial_pass'.format(name)]
        lxcrets = []
        for ogid in gids:
            lxcrets.append(
                bool(run_cmd(
                    name, 'test -e {0}'.format(gid),
                    stdout=False, stderr=False)))
        if True not in lxcrets:
            cret = set_pass(name,
                                            password=password, users=users)
            changes['250_password'] = 'Password updated\n'
            if not cret['result']:
                ret['result'] = False
                changes['250_password'] = 'Failed to update passwords\n'
            try:
                lxcret = int(
                    run_cmd(
                        name,
                        'sh -c \'touch "{0}"; '
                        'test -e "{0}";echo ${{?}}\''.format(gid)))
            except ValueError:
                lxcret = 1
            ret['result'] = not bool(lxcret)
            if not cret['result']:
                changes['250_password'] = 'Failed to test password file marker'
        comment += changes['250_password']
        if not ret['result']:
            ret['comment'] = comment
            return ret

    # set dns servers if any, only the first time
    if dnsservers:
        changes['350_dns'] = 'DNS in place\n'
        # retro compatibility, test also old markers
        gid = '/.lxc.initial_dns'
        gids = [gid,
                '/lxc.initial_dns',
                '/lxc.{0}.initial_dns'.format(name)]
        lxcrets = []
        for ogid in gids:
            lxcrets.append(bool(
                run_cmd(
                    name, 'test -e {0}'.format(ogid),
                    stdout=False, stderr=False)))
        if True not in lxcrets:
            cret = set_dns(name, dnsservers=dnsservers)
            changes['350_dns'] = 'DNS updated\n'
            if not cret['result']:
                ret['result'] = False
                changes['350_dns'] = 'DNS provisioning error\n'
            try:
                lxcret = int(
                    run_cmd(
                        name,
                        'sh -c \'touch "{0}"; '
                        'test -e "{0}";echo ${{?}}\''.format(gid)))
            except ValueError:
                lxcret = 1
            ret['result'] = not lxcret
            if not cret['result']:
                changes['350_dns'] = 'Failed to set DNS marker\n'
        comment += changes['350_dns']
        if not ret['result']:
            ret['comment'] = comment
            return ret

    if seed or seed_cmd:
        changes['450_seed'] = 'Container seeded\n'
        if seed:
            ret['seeded'] = bootstrap(
                name, config=salt_config,
                approve_key=approve_key,
                pub_key=pub_key, priv_key=priv_key,
                install=install,
                force_install=force_install,
                unconditional_install=unconditional_install,
                bootstrap_url=bootstrap_url,
                bootstrap_shell=bootstrap_shell,
                bootstrap_args=bootstrap_args)
        elif seed_cmd:
            lxc_info = info(name)
            rootfs = lxc_info['rootfs']
            ret['seeded'] = __salt__[seed_cmd](rootfs, name, salt_config)
        if not ret['seeded']:
            ret['result'] = False
            changes['450_seed'] = 'Seeding error\n'
        comment += changes['450_seed']
        if not ret['seeded']:
            ret['comment'] = comment
            ret['result'] = False
            return ret
    else:
        ret['seeded'] = True

    if not start_:
        stop(name)
        ret['state'] = 'stopped'
        comment += 'Container stopped\n'
    else:
        ret['state'] = state(name)
    ret['comment'] = comment
    ret['mid'] = name
    return ret


def cloud_init(name, vm_=None, **kwargs):
    '''
    Thin wrapper to lxc.init to be used from the saltcloud lxc driver

    name
        Name of the container
        may be None and then guessed from saltcloud mapping
    `vm_`
        saltcloud mapping defaults for the vm

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.cloud_init foo
    '''
    init_interface = cloud_init_interface(name, vm_, **kwargs)
    name = init_interface.pop('name', name)
    return init(name, **init_interface)


def create(name,
           config=None,
           profile=None,
           options=None,
           **kwargs):
    '''
    Create a new container.

    name
        Name of the container

    config
        The config file to use for the container. Defaults to system-wide
        config (usually in /etc/lxc/lxc.conf).

    profile
        Profile to use in container creation (see :mod:`lxc.get_profile
        <salt.modules.lxc.get_profile>`). Values in a profile will be
        overridden by the following parameters:

        * fstype
        * size
        * backing
        * vgname
        * lvname

        A profile can be passed either as the name of the profile, or a
        dictionary of variable names and values. See the :ref:`LXC Tutorial
        <tutorial-lxc-profiles>` for more information on how to use LXC
        profiles.

    template
        The template to use. E.g., 'ubuntu' or 'fedora'. Conflicts with the
        ``image`` argument.

    image
        A tar archive to use as the rootfs for the container. Conflicts with
        the ``template`` argument.

    backing
        The type of storage to use. Set to 'lvm' to use an LVM group. Defaults
        to filesystem within /var/lib/lxc/.

    vgnme
        Name of the LVM volume group in which to create the volume for this
        container. Only applicable if backing=lvm. Defaults to 'lxc'.
    fstype
        fstype to use on LVM lv.
    size
        Size of the volume to create. Only applicable if backing=lvm.
        Defaults to 1G.
    options
        Template specific options to pass to the lxc-create command.

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.create name [config=config_file] \\
                [profile=profile] [template=template_name] \\
                [backing=backing_store] [vgname=volume_group] \\
                [size=filesystem_size] [options=template_options]

    '''
    kwargs = copy.deepcopy(kwargs)
    if exists(name):
        raise CommandExecutionError(
            'Container \'{0}\' already exists'.format(name)
        )

    cmd = 'lxc-create -n {0}'.format(name)

    profile = copy.deepcopy(profile)
    if isinstance(profile, dict):
        profilename = profile.pop('name', None)
        profile = get_profile(profilename, **profile)
    else:
        profile = get_profile(profile)

    def select(key, default=None):
        kw_match = kwargs.pop(key, _marker)
        profile_match = profile.pop(key, default)
        # let kwargs be really be the preferred choice
        if kw_match is _marker:
            return profile_match
        return kw_match

    tvg = select('vgname')
    vgname = tvg if tvg else __salt__['config.get']('lxc.vgname')

    # The 'template' and 'image' params conflict
    template = select('template')
    image = select('image')
    if template and image:
        raise SaltInvocationError(
            'Only one of \'template\' and \'image\' is permitted'
        )

    backing = select('backing')
    if vgname and not backing:
        backing = 'lvm'
    lvname = select('lvname')
    fstype = select('fstype')
    size = select('size', '1G')
    if backing in ('dir', 'overlayfs', 'btrfs'):
        fstype = None
        size = None
    # some backends wont support some parameters
    if backing in ('aufs', 'dir', 'overlayfs', 'btrfs'):
        lvname = vgname = None

    if image:
        img_tar = __salt__['cp.cache_file'](image)
        template = os.path.join(
                os.path.dirname(salt.__file__),
                'templates',
                'lxc',
                'salt_tarball')
        profile['imgtar'] = img_tar
    if config:
        cmd += ' -f {0}'.format(config)
    if template:
        cmd += ' -t {0}'.format(template)
    if backing:
        backing = backing.lower()
        cmd += ' -B {0}'.format(backing)
        if backing in ('lvm',):
            if lvname:
                cmd += ' --lvname {0}'.format(vgname)
            if vgname:
                cmd += ' --vgname {0}'.format(vgname)
        if backing not in ('dir', 'overlayfs'):
            if fstype:
                cmd += ' --fstype {0}'.format(fstype)
            if size:
                cmd += ' --fssize {0}'.format(size)
    options = options or {}
    if profile:
        profile.update(options)
        options = profile

    if options:
        cmd += ' --'
        for key, val in options.items():
            cmd += ' --{0} {1}'.format(key, val)

    ret = __salt__['cmd.run_all'](cmd,
                                  python_shell=False,
                                  output_loglevel='trace')
    if ret['retcode'] == 0 and exists(name):
        __context__.pop('lxc.ls', None)
        return True
    else:
        if exists(name):
            # destroy the container if it was partially created
            cmd = 'lxc-destroy -n {0}'.format(name)
            __salt__['cmd.retcode'](cmd, python_shell=False)
        raise CommandExecutionError(
            'Container could not be created with cmd \'{0}\': {1}'
            .format(cmd, ret['stderr'])
        )


def clone(name,
          orig,
          snapshot=False,
          profile=None,
          **kwargs):
    '''
    Create a new container as a clone of another container

    name
        Name of the container.
    orig
        Name of the cloned original container
    snapshot
        Use Copy On Write snapshots (LVM)

    size
        Size of the container
    vgname
        LVM volume group(lxc)
    profile
        A LXC profile (defined in config or pillar)

    CLI Examples:

    .. code-block:: bash

        salt '*' lxc.clone myclone ubuntu snapshot=True
    '''
    if not isinstance(profile, dict):
        profile = _lxc_profile(profile)
    kwargs = copy.deepcopy(kwargs)
    profile = copy.deepcopy(profile)
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

    def select(k, default=None):
        kw = kwargs.pop(k, _marker)
        p = profile.pop(k, default)
        # let kwargs be really be the preferred choice
        if kw is _marker:
            kw = p
        return kw

    backing = select('backing')
    if backing in ['dir']:
        snapshot = False
    if not snapshot:
        snapshot = ''
    else:
        snapshot = '-s'

    cmd = 'lxc-clone {2} -o {0} -n {1}'.format(orig, name, snapshot)
    size = select('size', '1G')
    if backing in ['dir', 'overlayfs']:
        size = None
    if size:
        cmd += ' -L {0}'.format(size)
    if backing:
        cmd += ' -B {0}'.format(backing)

    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
    if ret['retcode'] == 0 and exists(name):
        return {'cloned': True}
    else:
        if exists(name):
            # destroy the container if it was partially created
            cmd = 'lxc-destroy -n {0}'.format(name)
            __salt__['cmd.retcode'](cmd, python_shell=False)
        log.warn('lxc-clone failed to create container')
        return {'cloned': False, 'error': (
            'container could not be created'
            ' with cmd "{0}": {1}'
        ).format(cmd, ret['stderr'])}


def ls_():
    '''
    Return just a list of the containers available

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.ls
    '''
    try:
        return __context__['lxc.ls']
    except KeyError:
        output = __salt__['cmd.run']('lxc-ls | sort -u', python_shell=True)
        __context__['lxc.ls'] = output.splitlines()
    return __context__['lxc.ls']


def list_(extra=False, limit=None):
    '''
    List containers classified by state

    extra
        Also get per-container specific info. This will change the return data.
        Instead of returning a list of containers, a dictionary of containers
        and each container's output from :mod:`lxc.info
        <salt.modules.lxc.info>`.

    limit
        Return output matching a specific state (**frozen**, **running**, or
        **stopped**).

        .. versionadded:: 2014.7.1

    CLI Examples:

    .. code-block:: bash

        salt '*' lxc.list
        salt '*' lxc.list extra=True
        salt '*' lxc.list limit=running
    '''
    ctnrs = ls()

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
        c_info = __salt__['cmd.run'](
            'lxc-info -n {0}'.format(container),
            python_shell=False,
            output_loglevel='debug'
        )
        c_state = None
        for line in c_info.splitlines():
            stat = line.split(':')
            if stat[0] in ('State', 'state'):
                c_state = stat[1].strip()
                break

        if not c_state or (limit is not None and c_state.lower() != limit):
            continue

        if extra:
            try:
                infos = info(container)
            except Exception:
                trace = traceback.format_exc()
                infos = {'error': 'Error while getting extra infos',
                         'comment': trace}
            method = 'update'
            value = {container: infos}
        else:
            method = 'append'
            value = container

        if c_state == 'STOPPED':
            getattr(stopped, method)(value)
            continue
        if c_state == 'FROZEN':
            getattr(frozen, method)(value)
            continue
        if c_state == 'RUNNING':
            getattr(running, method)(value)
            continue

    if limit is not None:
        return ret.get(limit, {} if extra else [])
    return ret


def _change_state(cmd, name, expected):
    pre = state(name)
    if pre is None:
        raise CommandExecutionError(
            'Container \'{0}\' does not exist'.format(name)
        )
    elif pre == expected:
        return {'state': expected,
                'result': True,
                'changes': {}}

    if cmd == 'lxc-destroy':
        # Kill the container first
        __salt__['cmd.run']('lxc-stop -k -n {0}'.format(name))

    cmd = '{0} -n {1}'.format(cmd, name)
    err = __salt__['cmd.run_stderr'](cmd, python_shell=False)
    if err:
        raise CommandExecutionError(
            'Error changing state for container \'{0}\' using command '
            '\'{1}\': {2}'.format(name, cmd, err)
        )
    if expected is not None:
        # some commands do not wait, so we will
        cmd = 'lxc-wait -n {0} -s {1}'.format(name, expected.upper())
        __salt__['cmd.run'](cmd, timeout=30)
    __context__.pop('lxc.state.{0}'.format(name), None)
    post = state(name)
    ret = {'state': post,
           'result': post == expected}
    if pre != post:
        ret['changes'] = {'old': pre, 'new': post}
    return ret


def _ensure_exists(name):
    '''
    Raise an exception if the container does not exist
    '''
    if not exists(name):
        raise CommandExecutionError(
            'Container \'{0}\' does not exist'.format(name)
        )


def _ensure_running(name, no_start=False):
    '''
    If the container is not currently running, start it. This function returns
    the state that the container was in before changing
    '''
    pre = state(name)
    if pre is None:
        return None
    ret = {}
    if pre == 'running':
        # This will be a no-op but running the function will give us a pretty
        # return dict.
        return start(name)
    elif pre == 'stopped':
        if no_start:
            return False
        return start(name)
    elif pre == 'frozen':
        if no_start:
            return False
        return unfreeze(name)


def start(name, restart=False):
    '''
    Start the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.start name
    '''
    _ensure_exists(name)
    if restart:
        __salt__['lxc.stop'](name)
    return _change_state('lxc-start -d', name, 'running')


def stop(name, kill=True):
    '''
    Stop the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.stop name
    '''
    _ensure_exists(name)
    cmd = 'lxc-stop'
    if kill:
        cmd += ' -k'
    return _change_state(cmd, name, 'stopped')


def freeze(name):
    '''
    Freeze the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.freeze name
    '''
    _ensure_exists(name)
    if state(name) == 'stopped':
        raise CommandExecutionError(
            'Container \'{0}\' is stopped'.format(name)
        )
    return _change_state('lxc-freeze', name, 'frozen')


def unfreeze(name):
    '''
    Unfreeze the named container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.unfreeze name
    '''
    _ensure_exists(name)
    if state(name) == 'stopped':
        raise CommandExecutionError(
            'Container \'{0}\' is stopped'.format(name)
        )
    return _change_state('lxc-unfreeze', name, 'running')


def destroy(name, stop=True):
    '''
    Destroy the named container.

    .. warning::

        Destroys all data associated with the container.

    CLI Examples:

    .. code-block:: bash

        salt '*' lxc.destroy foo
        salt '*' lxc.destroy foo stop=False
    '''
    if not stop and state(name) != 'stopped':
        raise CommandExecutionError(
            'Container \'{0}\' is not stopped'.format(name)
        )
    return _change_state('lxc-destroy', name, None)


def exists(name):
    '''
    Returns whether the named container exists.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.exists name
    '''
    return name in ls()


def state(name):
    '''
    Returns the state of a container.

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.state name
    '''
    # Don't use _ensure_exists() here, it will mess with _change_state()
    try:
        return __context__['lxc.state.{0}'.format(name)]
    except KeyError:
        if not exists(name):
            __context__['lxc.state.{0}'.format(name)] = None
        else:
            cmd = 'lxc-info -n {0}'.format(name)
            ret = __salt__['cmd.run_all'](cmd, python_shell=False)
            if ret['retcode'] != 0:
                __context__.pop('lxc.state.{0}'.format(name))
                raise CommandExecutionError(
                    'Unable to get state of container \'{0}\''.format(name)
                )
            c_infos = ret['stdout'].splitlines()
            c_state = None
            for c_info in c_infos:
                stat = c_info.split(':')
                if stat[0].lower() == 'state':
                    c_state = stat[1].strip().lower()
                    break
            __context__['lxc.state.{0}'.format(name)] = c_state
    return __context__['lxc.state.{0}'.format(name)]


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
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
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
    ret = __salt__['cmd.run_all'](cmd, python_shell=False)
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
    Returns information about a container

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.info name
    '''
    _ensure_exists(name)
    try:
        conf_file = os.path.join('/var/lib/lxc', name, 'config')
    except AttributeError:
        conf_file = os.path.join('/var/lib/lxc', str(name), 'config')

    if not os.path.isfile(conf_file):
        raise CommandExecutionError(
            'LXC config file {0} does not exist'.format(conf_file)
        )

    ret = {}
    config = []
    with salt.utils.fopen(conf_file) as fp_:
        for line in fp_:
            comps = [x.strip() for x in
                     line.split('#', 1)[0].strip().split('=', 1)]
            if len(comps) == 2:
                config.append(tuple(comps))

    ifaces = []
    current = None

    for key, val in config:
        if key == 'lxc.network.type':
            current = {'type': val}
            ifaces.append(current)
        elif not current:
            continue
        elif key.startswith('lxc.network.'):
            current[key.replace('lxc.network.', '', 1)] = val
    if ifaces:
        ret['nics'] = ifaces

    ret['rootfs'] = next((x[1] for x in config if x[0] == 'lxc.rootfs'), None)
    ret['state'] = state(name)
    ret['ips'] = []
    ret['public_ips'] = []
    ret['private_ips'] = []
    ret['public_ipv4_ips'] = []
    ret['public_ipv6_ips'] = []
    ret['private_ipv4_ips'] = []
    ret['private_ipv6_ips'] = []
    ret['ipv4_ips'] = []
    ret['ipv6_ips'] = []
    ret['size'] = None
    ret['config'] = conf_file

    if ret['state'] == 'running':
        try:
            limit = int(get_parameter(name, 'memory.limit_in_bytes').get(
                'memory.limit_in_bytes'))
        except (TypeError, ValueError):
            limit = 0
        try:
            usage = int(get_parameter(name, 'memory.usage_in_bytes').get(
                'memory.usage_in_bytes'))
        except (TypeError, ValueError):
            usage = 0
        free = limit - usage
        ret['memory_limit'] = limit
        ret['memory_free'] = free
        ret['size'] = run_cmd(name,
                              'df /|tail -n1|awk \'{{print $2}}\'',
                              python_shell=False)

        # First try iproute2
        ip_cmd = run_cmd(name, 'ip link show', output='all')
        if ip_cmd['retcode'] == 0:
            ip_data = ip_cmd['stdout']
            ip_cmd = run_cmd(name, 'ip addr show', output='all')
            ip_data += '\n' + ip_cmd['stdout']
            ip_data = salt.utils.network._interfaces_ip(ip_data)
        else:
            # That didn't work, try ifconfig
            ip_cmd = run_cmd(name, 'ifconfig', output='all')
            if ip_cmd['retcode'] == 0:
                ip_data = \
                    salt.utils.network._interfaces_ifconfig(ip_cmd['stdout'])
            else:
                # Neither was successful, give up
                log.warning(
                    'Unable to run ip or ifconfig in container \'{0}\''
                    .format(name)
                )
                ip_data = {}

        ret['ipv4_ips'] = salt.utils.network.ip_addrs(include_loopback=True,
                                                      interface_data=ip_data)
        ret['ipv6_ips'] = salt.utils.network.ip_addrs6(include_loopback=True,
                                                       interface_data=ip_data)
        ret['ips'] = ret['ipv4_ips'] + ret['ipv6_ips']
        for address in ret['ipv4_ips']:
            if address == '127.0.0.1':
                ret['private_ips'].append(address)
                ret['private_ipv4_ips'].append(address)
            elif salt.utils.cloud.is_public_ip(address):
                ret['public_ips'].append(address)
                ret['public_ipv4_ips'].append(address)
            else:
                ret['private_ips'].append(address)
                ret['private_ipv4_ips'].append(address)
        for address in ret['ipv6_ips']:
            if address == '::1' or address.startswith('fe80'):
                ret['private_ips'].append(address)
                ret['private_ipv6_ips'].append(address)
            else:
                ret['public_ips'].append(address)
                ret['public_ipv6_ips'].append(address)

    for key in [x for x in ret if x == 'ips' or x.endswith('ips')]:
        ret[key].sort(key=_ip_sort)
    return ret


def set_password(name, users, password, encrypted=True):
    '''
    .. versionchanged:: 2014.7.1
        Function renamed from ``set_pass`` to ``set_password``.

    Set the password of one or more system users inside containers

    CLI Example:

    .. code-block:: bash

        salt '*' lxc.set_pass container-name root '$6$uJ2uAyLU$KoI67t8As/0fXtJOPcHKGXmUpcoYUcVR2K6x93walnShTCQvjRwq25yIkiCBOqgbfdKQSFnAo28/ek6716vEV1'
        salt '*' lxc.set_pass container-name root foo encrypted=False

    '''
    def _bad_user_input():
        raise SaltInvocationError('Invalid input for \'users\' parameter')

    if not isinstance(users, list):
        try:
            users = users.split(',')
        except AttributeError:
            _bad_user_input()
    if not users:
        _bad_user_input()

    failed_users = []
    for user in users:
        result = run_cmd(name,
                         'chpasswd{0}'.format(' -e' if encrypted else ''),
                         stdin=':'.join((user, password)),
                         output='retcode',
                         python_shell=False,
                         output_loglevel='quiet')
        if result != 0:
            failed_users.append(user)
    if failed_users:
        raise CommandExecutionError(
            'Password change failed for the following user(s): {0}'
            .format(', '.join(failed_users))
        )
    return True

set_pass = set_password


def update_lxc_conf(name, lxc_conf, lxc_conf_unset):
    '''Edit LXC configuration options

    CLI Example:

    .. code-block:: bash

        salt-call -lall lxc.update_lxc_conf ubuntu \\
                lxc_conf="[{'network.ipv4.ip':'10.0.3.5'}]" \\
                lxc_conf_unset="['lxc.utsname']"

    '''
    changes = {'edited': [], 'added': [], 'removed': []}
    ret = {'changes': changes, 'result': True, 'comment': ''}
    lxc_conf_p = '/var/lib/lxc/{0}/config'.format(name)
    if not exists(name):
        ret['result'] = False
        ret['comment'] = 'Container does not exist: {0}'.format(name)
    elif not os.path.exists(lxc_conf_p):
        ret['result'] = False
        ret['comment'] = (
            'Configuration does not exist: {0}'.format(lxc_conf_p))
    else:
        with salt.utils.fopen(lxc_conf_p, 'r') as fic:
            filtered_lxc_conf = []
            for row in lxc_conf:
                if not row:
                    continue
                for conf in row:
                    try:
                        filtered_lxc_conf.append((conf.strip(),
                                                  row[conf].strip()))
                    except AttributeError:
                        filtered_lxc_conf.append((conf.strip(),
                                                  str(row[conf]).strip()))
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
                    if val not in lines:
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
                            and line not in dest_lxc_conf
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
                with salt.utils.fopen('{0}.{1}'.format(lxc_conf_p, chrono), 'w') as wfic:
                    wfic.write(conf)
                with salt.utils.fopen(lxc_conf_p, 'w') as wfic:
                    wfic.write(conf)
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
    '''
    .. versionchanged:: 2014.7.1
        The ``dnsservers`` and ``searchdomains`` parameters can now be passed
        as a comma-separated list.

    Update /etc/resolv.conf

    CLI Example:

    .. code-block:: bash

        salt myminion lxc.set_dns ubuntu "['8.8.8.8', '4.4.4.4']"

    '''
    ret = {'result': False}
    if dnsservers is None:
        dnsservers = ['8.8.8.8', '4.4.4.4']
    elif not isinstance(dnsservers, list):
        try:
            dnsservers = dnsservers.split(',')
        except AttributeError:
            raise SaltInvocationError(
                'Invalid input for \'dnsservers\' parameter'
            )
    if searchdomains is None:
        searchdomains = []
    elif not isinstance(searchdomains, list):
        try:
            searchdomains = searchdomains.split(',')
        except AttributeError:
            raise SaltInvocationError(
                'Invalid input for \'searchdomains\' parameter'
            )
    dns = ['nameserver {0}'.format(x) for x in dnsservers]
    dns.extend(['search {0}'.format(x) for x in searchdomains])
    dns = '\n'.join(dns) + '\n'
    result = run_cmd(name, 'tee /etc/resolv.conf', stdin=dns, output='all')
    if result['retcode'] != 0:
        error = ('Unable to write to /etc/resolv.conf in container \'{0}\''
                 .format(name))
        if result['stderr']:
            error += ': {0}'.format(result['stderr'])
        raise CommandExecutionError(error)
    return True


def bootstrap(name, config=None, approve_key=True,
              install=True,
              pub_key=None, priv_key=None,
              bootstrap_url=None,
              force_install=False,
              unconditional_install=False,
              bootstrap_args=None,
              bootstrap_shell=None):
    '''
    Install and configure salt in a container.

    config
        Minion configuration options. By default, the ``master`` option is set
        to the target host's master.

    approve_key
        Request a pre-approval of the generated minion key. Requires
        that the salt-master be configured to either auto-accept all keys or
        expect a signing request from the target host. Default: ``True``


    pub_key
        Explicit public key to pressed the minion with (optional).
        This can be either a filepath or a string representing the key

    priv_key
        Explicit private key to pressed the minion with (optional).
        This can be either a filepath or a string representing the key

    bootstrap_url
        url, content or filepath to the salt bootstrap script

    bootstrap_args
        salt bootstrap script arguments

    bootstrap_shell
        shell to execute the script into

    install
        Whether to attempt a full installation of salt-minion if needed.

    force_install
        Force installation even if salt-minion is detected,
        this is the way to run vendor bootstrap scripts even
        if a salt minion is already present in the container

    unconditional_install
        Run the script even if the container seems seeded

    CLI Examples:

    .. code-block:: bash

        salt '*' lxc.bootstrap ubuntu
        salt 'minion' lxc.bootstrap name [config=config_data] \\
                [approve_key=(True|False)] [install=(True|False)]
    '''

    infos = info(name)
    if not infos:
        return None
    # default set here as we cannot set them
    # in def as it can come from a chain of procedures.
    if not bootstrap_args:
        bootstrap_args = '-c {0}'
    if not bootstrap_shell:
        bootstrap_shell = 'sh'

    prior_state = _ensure_running(name)
    if not prior_state:
        return prior_state

    cmd = 'bash -c "if type salt-minion; then ' \
          'salt-call --local service.stop salt-minion; exit 0; ' \
          'else exit 1; fi"'
    if not force_install:
        # no need to run this cmd in force mode
        needs_install = bool(run_cmd(name, cmd, stdout=False))
    else:
        needs_install = True
    seeded = not run_cmd(
        name,
        'test -e \"{0}\"'.format(SEED_MARKER),
        stdout=False, stderr=False)
    tmp = tempfile.mkdtemp()
    if seeded and not unconditional_install:
        res = True
    else:
        res = False
        cfg_files = __salt__['seed.mkconfig'](
            config, tmp=tmp, id_=name, approve_key=approve_key,
            priv_key=priv_key, pub_key=pub_key)
        if needs_install or force_install or unconditional_install:
            if install:
                rstr = __salt__['test.rand_str']()
                configdir = '/tmp/.c_{0}'.format(rstr)
                run_cmd(name, 'install -m 0700 -d {0}'.format(configdir))
                bs_ = __salt__['config.gather_bootstrap_script'](
                    bootstrap=bootstrap_url)
                dest_dir = os.path.join('/tmp', rstr)
                for cmd in [
                    'mkdir -p {0}'.format(dest_dir),
                    'chmod 700 {0}'.format(dest_dir),
                ]:
                    if run_cmd(name, cmd, stdout=True):
                        log.error(
                            ('tmpdir {0} creation'
                             ' failed ({1}').format(dest_dir, cmd))
                        return False
                cp(name,
                   bs_,
                   '{0}/bootstrap.sh'.format(dest_dir))
                cp(name, cfg_files['config'],
                   os.path.join(configdir, 'minion'))
                cp(name, cfg_files['privkey'],
                   os.path.join(configdir, 'minion.pem'))
                cp(name, cfg_files['pubkey'],
                   os.path.join(configdir, 'minion.pub'))
                bootstrap_args = bootstrap_args.format(configdir)
                cmd = ("{0} -c 'PATH=$PATH:/bin:/sbin:/usr/sbin"
                       " {0} {2}/bootstrap.sh {1}'").format(
                           bootstrap_shell,
                           bootstrap_args.replace("'", "''"),
                           dest_dir)
                # log ASAP the forged bootstrap command which can be wrapped
                # out of the output in case of unexpected problem
                log.info('Running {0} in lxc {1}'.format(cmd, name))
                res = not run_cmd(
                    name, cmd,
                    stdout=True, stderr=True, use_vt=True)['retcode']
            else:
                res = False
        else:
            minion_config = salt.config.minion_config(cfg_files['config'])
            pki_dir = minion_config['pki_dir']
            cp(name, cfg_files['config'], '/etc/salt/minion')
            cp(name, cfg_files['privkey'], os.path.join(pki_dir, 'minion.pem'))
            cp(name, cfg_files['pubkey'], os.path.join(pki_dir, 'minion.pub'))
            run_cmd(name, 'salt-call --local service.enable salt-minion',
                    stdout=False)
            res = True
        shutil.rmtree(tmp)
        if prior_state == 'stopped':
            stop(name)
        elif prior_state == 'frozen':
            freeze(name)
        # mark seeded upon successful install
        if res:
            run_cmd(
                name, 'sh -c \'touch "{0}";\''.format(SEED_MARKER))
    return res


def attachable(name):
    '''
    Return True if the named container can be attached to via the lxc-attach
    command

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.attachable ubuntu
    '''
    _ensure_exists(name)
    # Can't use run_cmd() here because run_cmd uses attachable()
    cmd = 'lxc-attach --clear-env -n {0} -- /usr/bin/env'.format(name)
    return __salt__['cmd.retcode'](cmd, python_shell=False) == 0


def run_cmd(name,
            cmd,
            no_start=False,
            preserve_state=True,
            stdin=None,
            output='stdout',
            output_loglevel='debug',
            use_vt=False,
            keep_env='http_proxy,https_proxy,no_proxy'):
    '''
    Run a command inside a container

    name
        Name of the container on which to operate

    cmd
        Command to run

    no_start : False
        If the container is not running, don't start it

    preserve_state : True
        After running the command, return the container to its previous state

    stdin : None
        Standard input to be used for the command

        .. versionadded:: 2014.7.1

    output : stdout
        what type of output to display. valid values are: ``stdout``,
        ``stderr``, ``retcode``, or ``all``.

        .. versionadded:: 2014.7.1

    output_loglevel : debug
        Level at which to log the output from the command. Set to ``quiet`` to
        suppress logging.

        .. versionadded:: 2014.7.1

    use_vt : False
        Use SaltStack's utils.vt to stream output to console

    keep_env : http_proxy,https_proxy,no_proxy
        A list of env vars to preserve. May be passed as commma-delimited list.


    CLI Example:

    .. code-block:: bash

        salt myminion lxc.run_cmd mycontainer 'ifconfig -a'

    .. warning::

        Many shell builtins do not work, failing with an error similar to the
        one below:

        .. code-block:: bash

            $ salt myminion lxc.run_cmd foobar 'command -v bash' output=all
            myminion:
                ----------
                pid:
                    19498
                retcode:
                    255
                stderr:
                    lxc_container: No such file or directory - failed to exec 'command'
                stdout:
    '''
    _ensure_exists(name)
    valid_output = ('stdout', 'stderr', 'retcode', 'all')
    if output not in valid_output:
        raise SaltInvocationError(
            '\'output\' param must be one of the following: {0}'
            .format(', '.join(valid_output))
        )

    prior_state = _ensure_running(name, no_start=no_start)
    if not prior_state:
        return prior_state
    if attachable(name):
        if isinstance(keep_env, six.string_types):
            keep_env = keep_env.split(',')
        env = ' '.join('--set-var {0}={1}'.format(
                       x, pipes.quote(os.environ[x]))
                       for x in keep_env if x in os.environ)
        if 'PATH' not in keep_env:
            # --clear-env results in a very restrictive PATH, use the below #
            # path so that most commands won't fail.
            env += (
                ' --set-var PATH=/bin:/usr/bin:/sbin:/usr/sbin:/opt/bin:'
                '/usr/local/bin:/usr/local/sbin'
            )

        cmd = (
            'lxc-attach --clear-env {0} -n {1} -- {2}'
            .format(env, pipes.quote(name), cmd)
        )

        if not use_vt:
            ret = __salt__['cmd.run_all'](cmd,
                                          stdin=stdin,
                                          python_shell=False,
                                          output_loglevel=output_loglevel)
        else:
            stdout, stderr = '', ''
            try:
                proc = vt.Terminal(cmd,
                                   shell=True,
                                   log_stdin_level=output_loglevel,
                                   log_stdout_level=output_loglevel,
                                   log_stderr_level=output_loglevel,
                                   log_stdout=True,
                                   log_stderr=True,
                                   stream_stdout=True,
                                   stream_stderr=True)
                # consume output
                while proc.has_unread_data:
                    try:
                        time.sleep(0.5)
                        try:
                            cstdout, cstderr = proc.recv()
                        except IOError:
                            cstdout, cstderr = '', ''
                        if cstdout:
                            stdout += cstdout
                        else:
                            cstdout = ''
                        if cstderr:
                            stderr += cstderr
                        else:
                            cstderr = ''
                    except KeyboardInterrupt:
                        break
                ret = {'retcode': proc.exitstatus,
                       'pid': 2,
                       'stdout': stdout,
                       'stderr': stderr}
            except vt.TerminalException:
                trace = traceback.format_exc()
                log.error(trace)
                ret = {'retcode': 127,
                       'pid': '2',
                       'stdout': stdout,
                       'stderr': stderr}
            finally:
                proc.close(terminate=True, kill=True)
    else:
        rootfs = info(name).get('rootfs')
        ret = __salt__['cmd.run_chroot'](rootfs,
                                         cmd,
                                         stdin=stdin,
                                         python_shell=False,
                                         output_loglevel=output_loglevel)

    if preserve_state:
        if prior_state == 'stopped':
            stop(name)
        elif prior_state == 'frozen':
            freeze(name)

    if output == 'all':
        return ret
    return ret[output]


def _get_md5(name, path):
    '''
    Get the MD5 checksum of a file from a container
    '''
    try:
        return run_cmd(name, 'md5sum "{0}"'.format(path)).split()[0]
    except IndexError:
        # Destination file does not exist or could not be accessed
        return None


def cp(name, source, dest, source_hash=None, makedirs=False):
    '''
    Copy a file or directory from the host into a container.

    name
        Container name

    source
        File to be copied to the container

    dest
        Destination on the container. Must be an absolute path.

        .. versionchanged:: 2014.7.1
            If the destination is a directory, the file will be copied into
            that directory.

    makedirs : False

        Create the parent directory on the container if it does not already
        exist.

        .. versionadded:: 2014.7.1

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.cp /tmp/foo /root/foo
    '''
    c_state = state(name)
    if c_state != 'running':
        raise CommandExecutionError(
            'Container \'{0}\' {1}'.format(
                name,
                'is {0}'.format(c_state)
                    if c_state is not None
                    else 'does not exist'
            )
        )

    # Source file sanity checks
    if not os.path.isabs(source):
        raise SaltInvocationError('Source path must be absolute')
    elif not os.path.exists(source):
        raise SaltInvocationError(
            'Source file {0} does not exist'.format(source)
        )
    elif not os.path.isfile(source):
        raise SaltInvocationError('Source must be a regular file')
    source_dir, source_name = os.path.split(source)

    # Destination file sanity checks
    if not os.path.isabs(dest):
        raise SaltInvocationError('Destination path must be absolute')
    if run_cmd(name, 'test -d {0}'.format(dest), output='retcode') == 0:
        # Destination is a directory, full path to dest file will include the
        # basename of the source file.
        dest = os.path.join(dest, source_name)
    else:
        # Destination was not a directory. We will check to see if the parent
        # dir is a directory, and then (if makedirs=True) attempt to create the
        # parent directory.
        dest_dir, dest_name = os.path.split(dest)
        if run_cmd(name,
                   'test -d {0}'.format(dest_dir),
                   output='retcode') != 0:
            if makedirs:
                result = run_cmd(name,
                                 'mkdir -p "{0}"'.format(dest_dir),
                                 output='all')
                if result['retcode'] != 0:
                    error = ('Unable to create destination directory in '
                             'container \'{0}\''.format(name))
                    if result['stderr']:
                        error += ': {0}'.format(result['stderr'])
                    raise CommandExecutionError(error)
            else:
                raise SaltInvocationError(
                    'Directory {0} does not exist on container \'{1}\''
                    .format(dest_dir, name)
                )

    # Before we try to replace the file, compare checksums.
    source_md5 = __salt__['file.get_sum'](source, 'md5')
    if source_md5 != _get_md5(name, dest):
        run_cmd(name, 'cat "{0}" | tee "{1}"'.format(source, dest))
        return source_md5 == _get_md5(name, dest)
    # Checksums matched, no need to copy, just return True
    return True


def read_conf(conf_file, out_format='simple'):
    '''
    Read in an LXC configuration file. By default returns a simple, unsorted
    dict, but can also return a more detailed structure including blank lines
    and comments.

    CLI Examples:

    .. code-block:: bash

        salt 'minion' lxc.read_conf /etc/lxc/mycontainer.conf
        salt 'minion' lxc.read_conf /etc/lxc/mycontainer.conf out_format=commented
    '''
    ret_commented = []
    ret_simple = {}
    with salt.utils.fopen(conf_file, 'r') as fp_:
        for line in fp_.readlines():
            if '=' not in line:
                ret_commented.append(line)
                continue
            comps = line.split('=')
            value = '='.join(comps[1:]).strip()
            comment = None
            if value.strip().startswith('#'):
                vcomps = value.strip().split('#')
                value = vcomps[1].strip()
                comment = '#'.join(vcomps[1:]).strip()
                ret_commented.append({comps[0].strip(): {
                    'value': value,
                    'comment': comment,
                }})
            else:
                ret_commented.append({comps[0].strip(): value})
                ret_simple[comps[0].strip()] = value

    if out_format == 'simple':
        return ret_simple
    return ret_commented


def write_conf(conf_file, conf):
    '''
    Write out an LXC configuration file

    This is normally only used internally. The format of the data structure
    must match that which is returned from ``lxc.read_conf()``, with
    ``out_format`` set to ``commented``.

    An example might look like:

    .. code-block:: python

        [
            {'lxc.utsname': '$CONTAINER_NAME'},
            '# This is a commented line\\n',
            '\\n',
            {'lxc.mount': '$CONTAINER_FSTAB'},
            {'lxc.rootfs': {'comment': 'This is another test',
                            'value': 'This is another test'}},
            '\\n',
            {'lxc.network.type': 'veth'},
            {'lxc.network.flags': 'up'},
            {'lxc.network.link': 'br0'},
            {'lxc.network.hwaddr': '$CONTAINER_MACADDR'},
            {'lxc.network.ipv4': '$CONTAINER_IPADDR'},
            {'lxc.network.name': '$CONTAINER_DEVICENAME'},
        ]

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.write_conf /etc/lxc/mycontainer.conf \\
            out_format=commented
    '''
    if not isinstance(conf, list):
        return {'Error': 'conf must be passed in as a list'}

    with salt.utils.fopen(conf_file, 'w') as fp_:
        for line in conf:
            if isinstance(line, str):
                fp_.write(line)
            elif isinstance(line, dict):
                key = next(iter(list(line.keys())))
                out_line = None
                if isinstance(line[key], str):
                    out_line = ' = '.join((key, line[key]))
                elif isinstance(line[key], dict):
                    out_line = ' = '.join((key, line[key]['value']))
                    if 'comment' in line[key]:
                        out_line = ' # '.join((out_line, line[key]['comment']))
                if out_line:
                    fp_.write(out_line)
                    fp_.write('\n')
    return {}


def edit_conf(conf_file, out_format='simple', **kwargs):
    '''
    Edit an LXC configuration file. If a setting is already present inside the
    file, its value will be replaced. If it does not exist, it will be appended
    to the end of the file. Comments and blank lines will be kept in-tact if
    they already exist in the file.

    After the file is edited, its contents will be returned. By default, it
    will be returned in ``simple`` format, meaning an unordered dict (which
    may not represent the actual file order). Passing in an ``out_format`` of
    ``commented`` will return a data structure which accurately represents the
    order and content of the file.

    CLI Example:

    .. code-block:: bash

        salt 'minion' lxc.edit_conf /etc/lxc/mycontainer.conf \\
            out_format=commented lxc.network.type=veth
    '''
    data = []

    try:
        conf = read_conf(conf_file, out_format='commented')
    except Exception:
        conf = []

    for line in conf:
        if not isinstance(line, dict):
            data.append(line)
            continue
        else:
            key = next(iter(list(line.keys())))
            if key not in kwargs:
                data.append(line)
                continue
            data.append({key: kwargs[key]})
            del kwargs[key]

    for kwarg in kwargs:
        if kwarg.startswith('__'):
            continue
        data.append({kwarg: kwargs[kwarg]})

    write_conf(conf_file, data)
    return read_conf(conf_file, out_format)
