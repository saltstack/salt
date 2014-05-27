# -*- coding: utf-8 -*-
'''
Install Salt on an LXC Container
================================

.. versionadded:: Helium

Please read :ref:`core config documentation <config_lxc>`.
'''

# Import python libs
import json
import os
import logging
import copy
import time
from pprint import pformat

# Import salt libs
import salt.utils

# Import salt cloud libs
import salt.utils.cloud
import salt.config as config
from salt.cloud.exceptions import SaltCloudSystemExit

import salt.client
import salt.runner
import salt.syspaths


# Get logging started
log = logging.getLogger(__name__)

__FUN_TIMEOUT = {
    'cmd.run': 60 * 60,
    'test.ping': 10,
    'lxc.info': 40,
    'lxc.list': 300,
    'lxc.templates': 100,
    'grains.items': 100,
}
__CACHED_CALLS = {}
__CACHED_FUNS = {
    'test.ping': 3 * 60,  # cache ping for 3 minutes
    'lxc.list':  2  # cache lxc.list for 2 seconds
}


def __virtual__():
    '''
    Needs no special configuration
    '''
    return True


def _get_grain_id(id_):
    if not get_configured_provider():
        return
    infos = get_configured_provider()
    return 'salt.cloud.lxc.{0}.{1}'.format(infos['target'], id_)


def _minion_opts(cfg='minion'):
    if 'conf_file' in __opts__:
        default_dir = os.path.dirname(__opts__['conf_file'])
    else:
        default_dir = salt.syspaths.CONFIG_DIR,
    cfg = os.environ.get(
        'SALT_MINION_CONFIG', os.path.join(default_dir, cfg))
    opts = config.minion_config(cfg)
    return opts


def _master_opts(cfg='master'):
    cfg = os.environ.get(
        'SALT_MASTER_CONFIG',
        __opts__.get('conf_file',
                     os.path.join(salt.syspaths.CONFIG_DIR, cfg)))
    opts = config.master_config(cfg)
    return opts


def _client():
    return salt.client.get_local_client(mopts=_master_opts())


def _runner():
    # opts = _master_opts()
    # opts['output'] = 'quiet'
    return salt.runner.RunnerClient(_master_opts())


def _salt(fun, *args, **kw):
    '''Execute a salt function on a specific minion

    Special kwargs:

            salt_target
                target to exec things on
            salt_timeout
                timeout for jobs
            salt_job_poll
                poll interval to wait for job finish result
    '''
    try:
        poll = kw.pop('salt_job_poll')
    except KeyError:
        poll = 0.1
    try:
        target = kw.pop('salt_target')
    except KeyError:
        target = None
    try:
        timeout = int(kw.pop('salt_timeout'))
    except (KeyError, ValueError):
        # try to has some low timeouts for very basic commands
        timeout = __FUN_TIMEOUT.get(
            fun,
            900  # wait up to 15 minutes for the default timeout
        )
    try:
        kwargs = kw.pop('kwargs')
    except KeyError:
        kwargs = {}
    if not target:
        infos = get_configured_provider()
        if not infos:
            return
        target = infos['target']
    laps = time.time()
    cache = False
    if fun in __CACHED_FUNS:
        cache = True
        laps = laps // __CACHED_FUNS[fun]
    try:
        sargs = json.dumps(args)
    except TypeError:
        sargs = ''
    try:
        skw = json.dumps(kw)
    except TypeError:
        skw = ''
    try:
        skwargs = json.dumps(kwargs)
    except TypeError:
        skwargs = ''
    cache_key = (laps, target, fun, sargs, skw, skwargs)
    if not cache or (cache and (not cache_key in __CACHED_CALLS)):
        conn = _client()
        runner = _runner()
        rkwargs = kwargs.copy()
        rkwargs['timeout'] = timeout
        rkwargs.setdefault('expr_form', 'list')
        kwargs.setdefault('expr_form', 'list')
        jid = conn.cmd_async(tgt=target,
                             fun=fun,
                             arg=args,
                             kwarg=kw,
                             **rkwargs)
        cret = conn.cmd(tgt=target,
                        fun='saltutil.find_job',
                        arg=[jid],
                        timeout=10,
                        **kwargs)
        running = bool(cret.get(target, False))
        endto = time.time() + timeout
        while running:
            rkwargs = {
                'tgt': target,
                'fun': 'saltutil.find_job',
                'arg': [jid],
                'timeout': 10
            }
            cret = conn.cmd(**rkwargs)
            running = bool(cret.get(target, False))
            if not running:
                break
            if running and (time.time() > endto):
                raise Exception('Timeout {0}s for {1} is elapsed'.format(
                    timeout, pformat(rkwargs)))
            time.sleep(poll)
        # timeout for the master to return data about a specific job
        wait_for_res = float({
            'test.ping': '5',
        }.get(fun, '120'))
        while wait_for_res:
            wait_for_res -= 0.5
            cret = runner.cmd(
                'jobs.lookup_jid',
                [jid, {'__kwarg__': True}])
            if target in cret:
                ret = cret[target]
                break
            # special case, some answers may be crafted
            # to handle the unresponsivness of a specific command
            # which is also meaningfull, eg a minion not yet provisionned
            if fun in ['test.ping'] and not wait_for_res:
                ret = {
                    'test.ping': False,
                }.get(fun, False)
            time.sleep(0.5)
        try:
            if 'is not available.' in ret:
                raise SaltCloudSystemExit(
                    'module/function {0} is not available'.format(fun))
        except SaltCloudSystemExit:
            raise
        except TypeError:
            pass
        if cache:
            __CACHED_CALLS[cache_key] = ret
    elif cache and cache_key in __CACHED_CALLS:
        ret = __CACHED_CALLS[cache_key]
    return ret


def avail_images():
    return _salt('lxc.templates')


def list_nodes(conn=None, call=None):
    hide = False
    names = __opts__.get('names', [])
    profile = __opts__.get('profile', [])
    destroy_opt = __opts__.get('destroy', False)
    action = __opts__.get('action', '')
    for opt in ['full_query', 'select_query', 'query']:
        if __opts__.get(opt, False):
            call = 'full'
    if destroy_opt:
        call = 'full'
    if action and not call:
        call = 'action'
    if profile and names and not destroy_opt:
        hide = True
    if not get_configured_provider():
        return
    lxclist = _salt('lxc.list', extra=True)
    nodes = {}
    for state, lxcs in lxclist.items():
        for lxcc, linfos in lxcs.items():
            info = {
                'id': lxcc,
                'image': None,
                'size': linfos['size'],
                'state': state.lower(),
                'public_ips': linfos['public_ips'],
                'private_ips': linfos['private_ips'],
            }
            # in creation mode, we need to go inside the create method
            # so we hide the running vm from being seen as already installed
            # do not also mask half configured nodes which are explicitly asked
            # to be acted on, on the command line
            if (
                (call in ['full'] or not hide)
                and (
                    (lxcc in names and call in ['action'])
                    or (call in ['full'])
                )
            ):
                nodes[lxcc] = info
    return nodes


def list_nodes_full(conn=None, call=None):
    if not get_configured_provider():
        return
    if not call:
        call = 'action'
    return list_nodes(conn=conn, call=call)


def show_instance(name, call=None):
    '''
    Show the details from the provider concerning an instance
    '''

    if not get_configured_provider():
        return
    if not call:
        call = 'action'
    nodes = list_nodes_full(call=call)
    salt.utils.cloud.cache_node(nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def list_nodes_select(call=None):
    '''
    Return a list of the VMs that are on the provider, with select fields
    '''
    if not call:
        call = 'select'
    if not get_configured_provider():
        return
    info = ['id', 'image', 'size', 'state', 'public_ips', 'private_ips']
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(call='action'),
        __opts__.get('query.selection', info), call)


def _checkpoint(ret):
    sret = '''
id: {name}
last message: {comment}'''.format(**ret)
    keys = ret['changes'].items()
    keys.sort()
    for ch, comment in keys:
        sret += (
            '\n'
            '    {0}:\n'
            '      {1}'
        ).format(ch, comment.replace(
            '\n',
            '\n'
            '      '))
    if not ret['result']:
        if 'changes' in ret:
            del ret['changes']
        raise SaltCloudSystemExit(sret)
    log.info(sret)
    return sret


def destroy(vm_, call=None):
    '''Destroy a lxc container'''
    destroy_opt = __opts__.get('destroy', False)
    action = __opts__.get('action', '')
    if action != 'destroy' and not destroy_opt:
        raise SaltCloudSystemExit(
            'The destroy action must be called with -d, --destroy, '
            '-a or --action.'
        )
    if not get_configured_provider():
        return
    ret = {'comment': '{0} was not found'.format(vm_),
           'result': False}
    if _salt('lxc.info', vm_):
        salt.utils.cloud.fire_event(
            'event',
            'destroying instance',
            'salt/cloud/{0}/destroying'.format(vm_),
            {'name': vm_, 'instance_id': vm_},
            transport=__opts__['transport']
        )
        cret = _salt('lxc.destroy', vm_, stop=True)
        ret['result'] = cret['change']
        if ret['result']:
            ret['comment'] = '{0} was destroyed'.format(vm_)
            salt.utils.cloud.fire_event(
                'event',
                'destroyed instance',
                'salt/cloud/{0}/destroyed'.format(vm_),
                {'name': vm_, 'instance_id': vm_},
                transport=__opts__['transport']
            )
            if __opts__.get('update_cachedir', False) is True:
                salt.utils.cloud.delete_minion_cachedir(vm_, __active_provider_name__.split(':')[0], __opts__)
    return ret


def create(vm_, call=None):
    '''Create an lxc Container.
    This function is idempotent and will try to either provision
    or finish the provision of an lxc container.
    '''
    mopts = _master_opts()
    if not get_configured_provider(vm_):
        return
    __grains__ = _salt('grains.items')
    name = vm_['name']
    if not 'minion' in vm_:
        vm_['minion'] = {}
    minion = vm_['minion']

    from_container = vm_.get('from_container', None)
    image = vm_.get('image', None)
    vgname = vm_.get('vgname', None)
    backing = vm_.get('backing', None)
    snapshot = vm_.get('snapshot', False)
    profile = vm_.get('profile', None)
    fstype = vm_.get('fstype', None)
    dnsservers = vm_.get('dnsservers', [])
    lvname = vm_.get('lvname', None)
    ip = vm_.get('ip', None)
    mac = vm_.get('mac', None)
    netmask = vm_.get('netmask', '24')
    bridge = vm_.get('bridge', 'lxcbr0')
    gateway = vm_.get('gateway', 'auto')
    autostart = vm_.get('autostart', True)
    if autostart:
        autostart = "1"
    else:
        autostart = "0"
    size = vm_.get('size', '10G')
    ssh_username = vm_.get('ssh_username', 'user')
    sudo = vm_.get('sudo', True)
    password = vm_.get('password', 'user')
    lxc_conf_unset = vm_.get('lxc_conf_unset', [])
    lxc_conf = vm_.get('lxc_conf', [])
    stopped = vm_.get('stopped', False)
    master = vm_.get('master', None)
    script = vm_.get('script', None)
    script_args = vm_.get('script_args', None)
    users = vm_.get('users', None)
    # some backends wont support some parameters
    if backing not in ['lvm']:
        lvname = vgname = None
    if backing in ['dir', 'overlayfs']:
        fstype = None
        size = None
    if backing in ['dir']:
        snapshot = False
    for k in ['password',
              'ssh_username']:
        vm_[k] = locals()[k]

    salt.utils.cloud.fire_event(
        'event',
        'starting create',
        'salt/cloud/{0}/creating'.format(vm_['name']),
        {
            'name': vm_['name'],
            'profile': vm_['profile'],
            'provider': vm_['provider'],
        },
        transport=__opts__['transport']
    )
    if not dnsservers:
        dnsservers = ['8.8.8.8', '4.4.4.4']
    changes = {}
    changed = False
    ret = {'name': name,
           'changes': changes,
           'result': True,
           'comment': ''}
    if not users:
        users = ['root']
        if (
            __grains__['os'] in ['Ubuntu']
            and not 'ubuntu' in users
        ):
            users.append('ubuntu')
    if not ssh_username in users:
        users.append(ssh_username)
    if not users:
        users = []
    if not lxc_conf:
        lxc_conf = []
    if not lxc_conf_unset:
        lxc_conf_unset = []
    if from_container:
        method = 'clone'
    else:
        method = 'create'
    if ip is not None:
        lxc_conf.append({'lxc.network.ipv4': '{0}/{1}'.format(ip, netmask)})
        if mac is not None:
            lxc_conf.append({'lxc.network.hwaddr': mac})
        if gateway is not None:
            lxc_conf.append({'lxc.network.ipv4.gateway': gateway})
        if bridge is not None:
            lxc_conf.append({'lxc.network.link': bridge})
    lxc_conf.append({'lxc.start.auto': autostart})
    changes['100_creation'] = ''
    created = False
    cret = {'name': name, 'changes': {}, 'result': True, 'comment': ''}
    exists = _salt('lxc.exists', name)
    if exists:
        cret['comment'] = 'Container already exists'
        cret['result'] = True
    elif method == 'clone':
        oexists = _salt('lxc.exists', from_container)
        if not oexists:
            cret['result'] = False
            cret['comment'] = (
                'container could not be cloned: {0}, '
                '{1} does not exist'.format(name, from_container))
        else:
            nret = _salt('lxc.clone',
                         name,
                         orig=from_container,
                         snapshot=snapshot,
                         size=size,
                         backing=backing,
                         profile=profile)
            if nret.get('error', ''):
                cret['result'] = False
                cret['comment'] = '{0}\n{1}'.format(
                    nret['error'], 'Container cloning error')
            else:
                cret['result'] = (
                    nret['cloned']
                    or 'already exist' in cret.get('comment', ''))
                cret['comment'] += 'Container cloned\n'
                cret['changes']['status'] = 'cloned'
    elif method == 'create':
        nret = _salt('lxc.create',
                     name,
                     template=image,
                     profile=profile,
                     fstype=fstype,
                     vgname=vgname,
                     size=size,
                     lvname=lvname,
                     backing=backing)
        if nret.get('error', ''):
            cret['result'] = False
            cret['comment'] = nret['error']
        else:
            exists = (
                nret['created']
                or 'already exist' in nret.get('comment', ''))
            cret['comment'] += 'Container created\n'
            cret['changes']['status'] = 'Created'
    changes['100_creation'] = cret['comment']
    ret['comment'] = changes['100_creation']
    if not cret['result']:
        ret['result'] = False
        ret['comment'] = cret['comment']
    _checkpoint(ret)
    if cret['changes']:
        created = changed = True

    # edit lxc conf if any
    changes['150_conf'] = ''
    cret['result'] = False
    cret = _salt('lxc.update_lxc_conf',
                 name,
                 lxc_conf=lxc_conf,
                 lxc_conf_unset=lxc_conf_unset)
    if not cret['result']:
        ret['result'] = False
        ret['comment'] = cret['comment']
    _checkpoint(ret)
    if cret['changes']:
        changed = True
    changes['150_conf'] = 'lxc conf ok'

    # start
    changes['200_start'] = 'started'
    ret['comment'] = changes['200_start']
    # reboot if conf has changed
    cret = _salt('lxc.start', name, restart=changed)
    if not cret['result']:
        ret['result'] = False
        changes['200_start'] = cret['comment']
        ret['comment'] = changes['200_start']
    _checkpoint(ret)
    if cret['changes']:
        changed = True

    # first time provisionning only, set the default user/password
    changes['250_password'] = 'Passwords in place'
    ret['comment'] = changes['250_password']
    gid = '/.lxc.{0}.initial_pass'.format(name, False)
    lxcret = _salt('lxc.run_cmd',
                   name, 'test -e {0}'.format(gid),
                   stdout=False, stderr=False)
    if lxcret:
        cret = _salt('lxc.set_pass',
                     name,
                     password=password, users=users)
        changes['250_password'] = 'Password updated'
        if not cret['result']:
            ret['result'] = False
            changes['250_password'] = 'Failed to update passwords'
        ret['comment'] = changes['250_password']
        _checkpoint(ret)
        try:
            lxcret = int(
                _salt('lxc.run_cmd',
                      name,
                      'sh -c \'touch "{0}"; '
                      'test -e "{0}";echo ${{?}}\''.format(gid)))
        except ValueError:
            lxcret = 1
        ret['result'] = not bool(lxcret)
        if not cret['result']:
            changes['250_password'] = 'Failed to test password file marker'
        _checkpoint(ret)
        changed = True

    def wait_for_ip():
        '''
        Wait for the IP address to become available
        '''
        try:
            data = show_instance(vm_['name'], call='full')
        except Exception:
            data = {'private_ips': [], 'public_ips': []}
        ips = data['private_ips'] + data['public_ips']
        if ips:
            if ip and ip in ips:
                return ip
            return ips[0]
        time.sleep(1)
        return False
    ip = salt.utils.cloud.wait_for_fun(
        wait_for_ip,
        timeout=config.get_cloud_config_value(
            'wait_for_fun_timeout', vm_, __opts__, default=15 * 60))
    changes['300_ipattrib'] = 'Got ip {0}'.format(ip)
    if not ip:
        changes['300_ipattrib'] = 'Cant get ip'
        ret['result'] = False
    ret['comment'] = changes['300_ipattrib']
    _checkpoint(ret)

    # set dns servers
    changes['350_dns'] = 'DNS in place'
    ret['comment'] = changes['350_dns']
    gid = 'lxc.{0}.initial_dns'.format(name, False)
    lxcret = _salt('lxc.run_cmd',
                   name,
                   'test -e {0}'.format(gid),
                   stdout=False, stderr=False,)
    if dnsservers and not lxcret:
        cret = _salt('lxc.set_dns',
                     name,
                     dnsservers=dnsservers)
        changes['350_dns'] = 'DNS updated'
        ret['comment'] = changes['350_dns']
        if not cret['result']:
            ret['result'] = False
            changes['350_dns'] = 'DNS provisionning error'
            ret['comment'] = changes['350_dns']
        try:
            lxcret = int(
                _salt('lxc.run_cmd',
                      name,
                      'sh -c \'touch "{0}"; '
                      'test -e "{0}";echo ${{?}}\''.format(gid)))
        except ValueError:
            lxcret = 1
        ret['result'] = not lxcret
        if not cret['result']:
            changes['250_password'] = 'Failed to test DNS set marker'
        _checkpoint(ret)
        changed = True
    _checkpoint(ret)

    # provision salt on the fresh container
    if 'master' in minion:
        changes['400_salt'] = 'This vm is a salt minion'

        def testping(*args):
            ping = _salt('test.ping', **{'salt_target': vm_['name']})
            time.sleep(1)
            if ping:
                return 'OK'
            raise Exception('Unresponsive {0}'.format(vm_['name']))
        # if already created, test to ping before bindly go to saltify
        # we ping for 1 minute
        skip = False
        if not created:
            ping = salt.utils.cloud.wait_for_fun(testping, timeout=10)
            if ping == 'OK':
                skip = True

        if not skip:
            minion['master_port'] = mopts.get('ret_port', '4506')
            vm_['ssh_host'] = ip
            vm_['sudo'] = sudo
            vm_['sudo_password'] = password
            svm_ = copy.deepcopy(vm_)
            if 'gateway' in svm_:
                del svm_['gateway']
            if 'ssh_gateway' in vm_:
                svm_['gateway'] = ssh_gateway_opts = {}
                for k in ['ssh_gateway_key',
                          'ssh_gateway',
                          'ssh_gateway_user',
                          'ssh_gateway_port']:
                    val = vm_.get(k, None)
                    if val:
                        ssh_gateway_opts[ssh_gateway_opts.get(k, k)] = val
            sret = __salt__['saltify.create'](svm_)
            changes['400_salt'] = 'This vm is now a salt minion'
            if 'Error' in sret:
                ret['result'] = False
                changes['400_salt'] = pformat(sret['Error'])
            else:
                changed = True
        ret['comment'] = changes['400_salt']
        _checkpoint(ret)

        changes['401_salt'] = 'Minion is alive for salt commands'
        ping = salt.utils.cloud.wait_for_fun(testping, timeout=60)
        if ping != 'OK':
            ret['result'] = False
            changes['401_salt'] = 'Unresponsive minion!'
        ret['comment'] = changes['401_salt']
        _checkpoint(ret)

    sret = _checkpoint(ret)
    if not ret['result']:
        ret['Error'] = 'Error while creating {0}'.format(vm_['name'])
    if not changed and ret['result']:
        ret['changes'] = {}
        ret['comment'] = '\n{0}'.format(sret)
    return ret


def get_provider(name):
    data = None
    if name in __opts__['providers']:
        data = __opts__['providers'][name]
        if 'lxc' in data:
            data = data['lxc']
        else:
            data = None
    return data


def get_configured_provider(vm_=None):
    '''
    Return the contextual provider of None if no configured
    one can be found.
    '''
    if vm_ is None:
        vm_ = {}
    dalias, driver = __active_provider_name__.split(':')
    data = None
    tgt = 'unknown'
    img_provider = __opts__.get('list_images', '')
    arg_providers = __opts__.get('names', [])
    matched = False
    # --list-images level
    if img_provider:
        tgt = 'provider: {0}'.format(img_provider)
        if dalias == img_provider:
            data = get_provider(img_provider)
            matched = True
    # providers are set in configuration
    if not data and not 'profile' in __opts__ and arg_providers:
        for name in arg_providers:
            tgt = 'provider: {0}'.format(name)
            if dalias == name:
                data = get_provider(name)
            if data:
                matched = True
                break
    # -p is providen, get the uplinked provider
    elif 'profile' in __opts__:
        curprof = __opts__['profile']
        profs = __opts__['profiles']
        tgt = 'profile: {0}'.format(curprof)
        if (
            curprof in profs
            and profs[curprof]['provider'] == __active_provider_name__
        ):
            prov, cdriver = profs[curprof]['provider'].split(':')
            tgt += ' provider: {0}'.format(prov)
            data = get_provider(prov)
            matched = True
    # fallback if we have only __active_provider_name__
    if ((__opts__.get('destroy', False) and not data)
        or (not matched and __active_provider_name__)):
        data = __opts__.get('providers',
                           {}).get(dalias, {}).get(driver, {})
    # in all cases, verify that the linked saltmaster is alive.
    if data:
        try:
            ret = _salt('test.ping', salt_target=data['target'])
            if not ret:
                raise Exception('error')
            return data
        except Exception:
            raise SaltCloudSystemExit(
                'Configured provider {0} minion: {1} is unreachable'.format(
                    __active_provider_name__, data['target']))
    return False
