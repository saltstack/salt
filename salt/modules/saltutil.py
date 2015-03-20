# -*- coding: utf-8 -*-
'''
The Saltutil module is used to manage the state of the salt minion itself. It
is used to manage minion modules as well as automate updates to the salt
minion.

:depends:   - esky Python module for update functionality
'''

# Import python libs
import os
import shutil
import signal
import logging
import fnmatch
import time
import sys
import copy
from urllib2 import URLError

# Fix a nasty bug with Win32 Python not supporting all of the standard signals
try:
    salt_SIGKILL = signal.SIGKILL
except AttributeError:
    salt_SIGKILL = signal.SIGTERM

# Import salt libs
import salt
import salt.payload
import salt.state
import salt.client
import salt.config
import salt.runner
import salt.utils
import salt.utils.process
import salt.utils.minion
import salt.transport
import salt.wheel
from salt.exceptions import (
    SaltReqTimeoutError, SaltRenderError, CommandExecutionError
)
from salt._compat import string_types

__proxyenabled__ = ['*']

# Import third party libs
try:
    import esky
    from esky import EskyVersionError
    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False

log = logging.getLogger(__name__)


def _get_top_file_envs():
    '''
    Get all environments from the top file
    '''
    try:
        return __context__['saltutil._top_file_envs']
    except KeyError:
        try:
            st_ = salt.state.HighState(__opts__)
            top = st_.get_top()
            if top:
                envs = st_.top_matches(top).keys() or 'base'
            else:
                envs = 'base'
        except SaltRenderError as exc:
            raise CommandExecutionError(
                'Unable to render top file(s): {0}'.format(exc)
            )
        __context__['saltutil._top_file_envs'] = envs
        return envs


def _sync(form, saltenv=None):
    '''
    Sync the given directory in the given environment
    '''
    if saltenv is None:
        saltenv = _get_top_file_envs()
    if isinstance(saltenv, string_types):
        saltenv = saltenv.split(',')
    ret = []
    remote = set()
    source = os.path.join('salt://_{0}'.format(form))
    mod_dir = os.path.join(__opts__['extension_modules'], '{0}'.format(form))
    if not os.path.isdir(mod_dir):
        log.info('Creating module dir {0!r}'.format(mod_dir))
        try:
            os.makedirs(mod_dir)
        except (IOError, OSError):
            msg = 'Cannot create cache module directory {0}. Check permissions.'
            log.error(msg.format(mod_dir))
    for sub_env in saltenv:
        log.info('Syncing {0} for environment {1!r}'.format(form, sub_env))
        cache = []
        log.info('Loading cache from {0}, for {1})'.format(source, sub_env))
        # Grab only the desired files (.py, .pyx, .so)
        cache.extend(
            __salt__['cp.cache_dir'](
                source, sub_env, include_pat=r'E@\.(pyx?|so)$'
            )
        )
        local_cache_dir = os.path.join(
                __opts__['cachedir'],
                'files',
                sub_env,
                '_{0}'.format(form)
                )
        log.debug('Local cache dir: {0!r}'.format(local_cache_dir))
        for fn_ in cache:
            relpath = os.path.relpath(fn_, local_cache_dir)
            relname = os.path.splitext(relpath)[0].replace(os.sep, '.')
            remote.add(relpath)
            dest = os.path.join(mod_dir, relpath)
            log.info('Copying {0!r} to {1!r}'.format(fn_, dest))
            if os.path.isfile(dest):
                # The file is present, if the sum differs replace it
                hash_type = __opts__.get('hash_type', 'md5')
                src_digest = salt.utils.get_hash(fn_, hash_type)
                dst_digest = salt.utils.get_hash(dest, hash_type)
                if src_digest != dst_digest:
                    # The downloaded file differs, replace!
                    shutil.copyfile(fn_, dest)
                    ret.append('{0}.{1}'.format(form, relname))
            else:
                dest_dir = os.path.dirname(dest)
                if not os.path.isdir(dest_dir):
                    os.makedirs(dest_dir)
                shutil.copyfile(fn_, dest)
                ret.append('{0}.{1}'.format(form, relname))

    touched = bool(ret)
    if __opts__.get('clean_dynamic_modules', True):
        current = set(_listdir_recursively(mod_dir))
        for fn_ in current - remote:
            full = os.path.join(mod_dir, fn_)
            if os.path.isfile(full):
                touched = True
                os.remove(full)
        # Cleanup empty dirs
        while True:
            emptydirs = _list_emptydirs(mod_dir)
            if not emptydirs:
                break
            for emptydir in emptydirs:
                touched = True
                os.rmdir(emptydir)
    # Dest mod_dir is touched? trigger reload if requested
    if touched:
        mod_file = os.path.join(__opts__['cachedir'], 'module_refresh')
        with salt.utils.fopen(mod_file, 'a+') as ofile:
            ofile.write('')
    return ret


def _listdir_recursively(rootdir):
    file_list = []
    for root, dirs, files in os.walk(rootdir):
        for filename in files:
            relpath = os.path.relpath(root, rootdir).strip('.')
            file_list.append(os.path.join(relpath, filename))
    return file_list


def _list_emptydirs(rootdir):
    emptydirs = []
    for root, dirs, files in os.walk(rootdir):
        if not files and not dirs:
            emptydirs.append(root)
    return emptydirs


def update(version=None):
    '''
    Update the salt minion from the URL defined in opts['update_url']
    SaltStack, Inc provides the latest builds here:
    update_url: http://docs.saltstack.com/downloads/

    Be aware that as of 2014-8-11 there's a bug in esky such that only the
    latest version available in the update_url can be downloaded and installed.

    This feature requires the minion to be running a bdist_esky build.

    The version number is optional and will default to the most recent version
    available at opts['update_url'].

    Returns details about the transaction upon completion.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.update
        salt '*' saltutil.update 0.10.3
    '''
    ret = {}
    if not HAS_ESKY:
        ret['_error'] = 'Esky not available as import'
        return ret
    if not getattr(sys, 'frozen', False):
        ret['_error'] = 'Minion is not running an Esky build'
        return ret
    if not __salt__['config.option']('update_url'):
        ret['_error'] = '"update_url" not configured on this minion'
        return ret
    app = esky.Esky(sys.executable, __opts__['update_url'])
    oldversion = __grains__['saltversion']
    if not version:
        try:
            version = app.find_update()
        except URLError as exc:
            ret['_error'] = 'Could not connect to update_url. Error: {0}'.format(exc)
            return ret
    if not version:
        ret['_error'] = 'No updates available'
        return ret
    try:
        app.fetch_version(version)
    except EskyVersionError as exc:
        ret['_error'] = 'Unable to fetch version {0}. Error: {1}'.format(version, exc)
        return ret
    try:
        app.install_version(version)
    except EskyVersionError as exc:
        ret['_error'] = 'Unable to install version {0}. Error: {1}'.format(version, exc)
        return ret
    try:
        app.cleanup()
    except Exception as exc:
        ret['_error'] = 'Unable to cleanup. Error: {0}'.format(exc)
    restarted = {}
    for service in __opts__['update_restart_services']:
        restarted[service] = __salt__['service.restart'](service)
    ret['comment'] = 'Updated from {0} to {1}'.format(oldversion, version)
    ret['restarted'] = restarted
    return ret


def sync_modules(saltenv=None, refresh=True):
    '''
    Sync the modules from the _modules directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _modules directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_modules
    '''
    ret = _sync('modules', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_states(saltenv=None, refresh=True):
    '''
    Sync the states from the _states directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _states directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_states
    '''
    ret = _sync('states', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_grains(saltenv=None, refresh=True):
    '''
    Sync the grains from the _grains directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _grains directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_grains
    '''
    ret = _sync('grains', saltenv)
    if refresh:
        refresh_modules()
        refresh_pillar()
    return ret


def sync_renderers(saltenv=None, refresh=True):
    '''
    Sync the renderers from the _renderers directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _renderers directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_renderers
    '''
    ret = _sync('renderers', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_returners(saltenv=None, refresh=True):
    '''
    Sync the returners from the _returners directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _returners directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_returners
    '''
    ret = _sync('returners', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_outputters(saltenv=None, refresh=True):
    '''
    Sync the outputters from the _outputters directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _outputters directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_outputters
    '''
    ret = _sync('outputters', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_utils(saltenv=None, refresh=True):
    '''
    Sync utility source files from the _utils directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _utils directory, base is the default
    environment.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_utils
    '''
    ret = _sync('utils', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_all(saltenv=None, refresh=True):
    '''
    Sync down all of the dynamic modules from the file server for a specific
    environment

    refresh : True
        Also refresh the execution modules available to the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_all
    '''
    log.debug('Syncing all')
    ret = {}
    ret['modules'] = sync_modules(saltenv, False)
    ret['states'] = sync_states(saltenv, False)
    ret['grains'] = sync_grains(saltenv, False)
    ret['renderers'] = sync_renderers(saltenv, False)
    ret['returners'] = sync_returners(saltenv, False)
    ret['outputters'] = sync_outputters(saltenv, False)
    ret['utils'] = sync_utils(saltenv, False)
    if refresh:
        refresh_modules()
    return ret


def refresh_pillar():
    '''
    Signal the minion to refresh the pillar data.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_pillar
    '''
    return __salt__['event.fire']({}, 'pillar_refresh')


def refresh_modules():
    '''
    Signal the minion to refresh the module and grain data

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_modules
    '''
    return __salt__['event.fire']({}, 'module_refresh')


def is_running(fun):
    '''
    If the named function is running return the data associated with it/them.
    The argument can be a glob

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.is_running state.highstate
    '''
    run = running()
    ret = []
    for data in run:
        if fnmatch.fnmatch(data.get('fun', ''), fun):
            ret.append(data)
    return ret


def running():
    '''
    Return the data on all running salt processes on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.running
    '''
    return salt.utils.minion.running(__opts__)


def clear_cache():
    '''
    Forcibly removes all caches on a minion.

    .. versionadded:: 2014.7.0

    WARNING: The safest way to clear a minion cache is by first stopping
    the minion and then deleting the cache files before restarting it.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.clear_cache
    '''
    for root, dirs, files in salt.utils.safe_walk(__opts__['cachedir'], followlinks=False):
        for name in files:
            try:
                os.remove(os.path.join(root, name))
            except OSError as exc:
                log.error('Attempt to clear cache with saltutil.clear_cache FAILED with: {0}'.format(exc))
                return False
    return True


def find_job(jid):
    '''
    Return the data for a specific job id

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.find_job <job id>
    '''
    for data in running():
        if data['jid'] == jid:
            return data
    return {}


def find_cached_job(jid):
    '''
    Return the data for a specific cached job id

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.find_cached_job <job id>
    '''
    serial = salt.payload.Serial(__opts__)
    proc_dir = os.path.join(__opts__['cachedir'], 'minion_jobs')
    job_dir = os.path.join(proc_dir, str(jid))
    if not os.path.isdir(job_dir):
        return
    path = os.path.join(job_dir, 'return.p')
    with salt.utils.fopen(path, 'rb') as fp_:
        buf = fp_.read()
        fp_.close()
        if buf:
            data = serial.loads(buf)
        else:
            return
    if not isinstance(data, dict):
        # Invalid serial object
        return
    return data


def signal_job(jid, sig):
    '''
    Sends a signal to the named salt job's process

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.signal_job <job id> 15
    '''
    for data in running():
        if data['jid'] == jid:
            try:
                os.kill(int(data['pid']), sig)
                if 'child_pids' in data:
                    for pid in data['child_pids']:
                        os.kill(int(pid), sig)
                return 'Signal {0} sent to job {1} at pid {2}'.format(
                        int(sig),
                        jid,
                        data['pid']
                        )
            except OSError:
                path = os.path.join(__opts__['cachedir'], 'proc', str(jid))
                if os.path.isfile(path):
                    os.remove(path)
                return ('Job {0} was not running and job data has been '
                        ' cleaned up').format(jid)
    return ''


def term_job(jid):
    '''
    Sends a termination signal (SIGTERM 15) to the named salt job's process

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.term_job <job id>
    '''
    return signal_job(jid, signal.SIGTERM)


def kill_job(jid):
    '''
    Sends a kill signal (SIGKILL 9) to the named salt job's process

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.kill_job <job id>
    '''
    # Some OS's (Win32) don't have SIGKILL, so use salt_SIGKILL which is set to
    # an appropriate value for the operating system this is running on.
    return signal_job(jid, salt_SIGKILL)


def regen_keys():
    '''
    Used to regenerate the minion keys.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.regen_keys
    '''
    for fn_ in os.listdir(__opts__['pki_dir']):
        path = os.path.join(__opts__['pki_dir'], fn_)
        try:
            os.remove(path)
        except os.error:
            pass
    time.sleep(60)
    sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = salt.crypt.SAuth(__opts__)


def revoke_auth():
    '''
    The minion sends a request to the master to revoke its own key.
    Note that the minion session will be revoked and the minion may
    not be able to return the result of this command back to the master.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.revoke_auth
    '''
    # sreq = salt.payload.SREQ(__opts__['master_uri'])
    auth = salt.crypt.SAuth(__opts__)
    tok = auth.gen_token('salt')
    load = {'cmd': 'revoke_auth',
            'id': __opts__['id'],
            'tok': tok}

    sreq = salt.transport.Channel.factory(__opts__)
    try:
        sreq.send(load)
        # return auth.crypticle.loads(
        #         sreq.send('aes', auth.crypticle.dumps(load), 1))
    except SaltReqTimeoutError:
        return False
    return False


def _get_ssh_or_api_client(cfgfile, ssh=False):
    if ssh:
        client = salt.client.SSHClient(cfgfile)
    else:
        client = salt.client.get_local_client(cfgfile)
    return client


def _exec(client, tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs):
    ret = {}
    seen = 0
    for ret_comp in client.cmd_iter(
            tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs):
        ret.update(ret_comp)
        seen += 1
        # ret can be empty, so we cannot len the whole return dict
        if expr_form == 'list' and len(tgt) == seen:
            # do not wait for timeout when explicit list matching
            # and all results are there
            break
    return ret


def cmd(tgt,
        fun,
        arg=(),
        timeout=None,
        expr_form='glob',
        ret='',
        kwarg=None,
        ssh=False,
        **kwargs):
    '''
    Assuming this minion is a master, execute a salt command

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.cmd
    '''
    cfgfile = __opts__['conf_file']
    client = _get_ssh_or_api_client(cfgfile, ssh)
    ret = _exec(
        client, tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs)
    # if return is empty, we may have not used the right conf,
    # try with the 'minion relative master configuration counter part
    # if available
    master_cfgfile = '{0}master'.format(cfgfile[:-6])  # remove 'minion'
    if (
        not ret
        and cfgfile.endswith('{0}{1}'.format(os.path.sep, 'minion'))
        and os.path.exists(master_cfgfile)
    ):
        client = _get_ssh_or_api_client(master_cfgfile, ssh)
        ret = _exec(
            client, tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs)
    return ret


def cmd_iter(tgt,
             fun,
             arg=(),
             timeout=None,
             expr_form='glob',
             ret='',
             kwarg=None,
             ssh=False,
             **kwargs):
    '''
    Assuming this minion is a master, execute a salt command

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.cmd
    '''
    if ssh:
        client = salt.client.SSHClient(__opts__['conf_file'])
    else:
        client = salt.client.get_local_client(__opts__['conf_file'])
    for ret in client.cmd_iter(
            tgt,
            fun,
            arg,
            timeout,
            expr_form,
            ret,
            kwarg,
            **kwargs):
        yield ret


def runner(fun, **kwargs):
    '''
    Execute a runner module (this function must be run on the master)

    .. versionadded:: 2014.7

    name
        The name of the function to run
    kwargs
        Any keyword arguments to pass to the runner function

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.runner jobs.list_jobs
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)

    if 'master_job_cache' not in __opts__:
        master_config = os.path.join(os.path.dirname(__opts__['conf_file']),
                                     'master')
        master_opts = salt.config.master_config(master_config)
        rclient = salt.runner.RunnerClient(master_opts)
    else:
        rclient = salt.runner.RunnerClient(__opts__)

    return rclient.cmd(fun, [], kwarg=kwargs)


def wheel(fun, **kwargs):
    '''
    Execute a wheel module (this function must be run on the master)

    .. versionadded:: 2014.7

    name
        The name of the function to run
    kwargs
        Any keyword arguments to pass to the wheel function

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.wheel key.accept match=jerry
    '''
    wclient = salt.wheel.WheelClient(__opts__)
    return wclient.cmd(fun, **kwargs)


# this is the only way I could figure out how to get the REAL file_roots
# __opt__['file_roots'] is set to  __opt__['pillar_root']
class _MMinion(object):
    def __new__(cls, saltenv, reload_env=False):
        # this is to break out of salt.loaded.int and make this a true singleton
        # hack until https://github.com/saltstack/salt/pull/10273 is resolved
        # this is starting to look like PHP
        global _mminions  # pylint: disable=W0601
        if '_mminions' not in globals():
            _mminions = {}
        if saltenv not in _mminions or reload_env:
            opts = copy.deepcopy(__opts__)
            del opts['file_roots']
            # grains at this point are in the context of the minion
            global __grains__  # pylint: disable=W0601
            grains = copy.deepcopy(__grains__)
            m = salt.minion.MasterMinion(opts)

            # this assignment is so that the rest of fxns called by salt still
            # have minion context
            __grains__ = grains

            # this assignment is so that fxns called by mminion have minion
            # context
            m.opts['grains'] = grains

            env_roots = m.opts['file_roots'][saltenv]
            m.opts['module_dirs'] = [fp + '/_modules' for fp in env_roots]
            m.gen_modules()
            _mminions[saltenv] = m
        return _mminions[saltenv]


def mmodule(saltenv, fun, *args, **kwargs):
    '''
    Loads minion modules from an environment so that they can be used in pillars
    for that environment

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.mmodule base test.ping
    '''
    mminion = _MMinion(saltenv)
    return mminion.functions[fun](*args, **kwargs)
