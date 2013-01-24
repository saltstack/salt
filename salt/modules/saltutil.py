'''
The Saltutil module is used to manage the state of the salt minion itself. It
is used to manage minion modules as well as automate updates to the salt minion

:depends:   - esky Python module for update functionality
'''

# Import python libs
import os
import hashlib
import shutil
import signal
import logging
import fnmatch
import sys

# Import salt libs
import salt.payload
import salt.state
from salt._compat import string_types

# Import third party libs
try:
    import esky
    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False

log = logging.getLogger(__name__)


def _sync(form, env=None):
    '''
    Sync the given directory in the given environment
    '''
    if env is None:
        # No environment passed, detect them based on gathering the top files
        # from the master
        env = 'base'
        st_ = salt.state.HighState(__opts__)
        top = st_.get_top()
        if top:
            env = st_.top_matches(top).keys()
    if isinstance(env, string_types):
        env = env.split(',')
    ret = []
    remote = set()
    source = os.path.join('salt://_{0}'.format(form))
    mod_dir = os.path.join(__opts__['extension_modules'], '{0}'.format(form))
    if not os.path.isdir(mod_dir):
        log.info('Creating module dir \'{0}\''.format(mod_dir))
        os.makedirs(mod_dir)
    for sub_env in env:
        log.info('Syncing {0} for environment \'{1}\''.format(form, sub_env))
        cache = []
        log.info('Loading cache from {0}, for {1})'.format(source, sub_env))
        cache.extend(__salt__['cp.cache_dir'](source, sub_env))
        local_cache_dir = os.path.join(
                __opts__['cachedir'],
                'files',
                sub_env,
                '_{0}'.format(form)
                )
        log.debug('Local cache dir: \'{0}\''.format(local_cache_dir))
        for fn_ in cache:
            if __opts__.get('file_client', '') == 'local':
                for fn_root in __opts__['file_roots'].get(sub_env, []):
                    if fn_.startswith(fn_root):
                        relpath = os.path.relpath(fn_, fn_root)
                        relpath = relpath[relpath.index('/') + 1:]
                        relname = os.path.splitext(relpath)[0].replace(
                                os.sep,
                                '.')
                        remote.add(relpath)
                        dest = os.path.join(mod_dir, relpath)
            else:
                relpath = os.path.relpath(fn_, local_cache_dir)
                relname = os.path.splitext(relpath)[0].replace(os.sep, '.')
                remote.add(relpath)
                dest = os.path.join(mod_dir, relpath)
            log.info('Copying \'{0}\' to \'{1}\''.format(fn_, dest))
            if os.path.isfile(dest):
                # The file is present, if the sum differs replace it
                srch = hashlib.md5(
                    salt.utils.fopen(fn_, 'r').read()
                ).hexdigest()
                dsth = hashlib.md5(
                    salt.utils.fopen(dest, 'r').read()
                ).hexdigest()
                if srch != dsth:
                    # The downloaded file differes, replace!
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
        #cleanup empty dirs
        while True:
            emptydirs = _list_emptydirs(mod_dir)
            if not emptydirs:
                break
            for emptydir in emptydirs:
                touched = True
                os.rmdir(emptydir)
    #dest mod_dir is touched? trigger reload if requested
    if touched:
        mod_file = os.path.join(__opts__['cachedir'], 'module_refresh')
        with salt.utils.fopen(mod_file, 'a+') as ofile:
            ofile.write('')
    return ret


def _listdir_recursively(rootdir):
    file_list = []
    for root, sub_folders, files in os.walk(rootdir):
        for file in files:
            relpath = os.path.relpath(root, rootdir).strip('.')
            file_list.append(os.path.join(relpath, file))
    return file_list


def _list_emptydirs(rootdir):
    emptydirs = []
    for root, sub_folders, files in os.walk(rootdir):
        if not files and not sub_folders:
            emptydirs.append(root)
    return emptydirs


def update(version=None):
    '''
    Update the salt minion from the url defined in opts['update_url']


    This feature requires the minion to be running a bdist_esky build.

    The version number is optional and will default to the most recent version
    available at opts['update_url'].

    Returns details about the transaction upon completion.

    CLI Example::

        salt '*' saltutil.update 0.10.3
    '''
    if not HAS_ESKY:
        return 'Esky not available as import'
    if not getattr(sys, 'frozen', False):
        return 'Minion is not running an Esky build'
    if not __salt__['config.option']('update_url'):
        return '"update_url" not configured on this minion'
    app = esky.Esky(sys.executable, __opts__['update_url'])
    oldversion = __grains__['saltversion']
    try:
        if not version:
            version = app.find_update()
        if not version:
            return 'No updates available'
        app.fetch_version(version)
        app.install_version(version)
        app.cleanup()
    except Exception as err:
        return err
    restarted = {}
    for service in __opts__['update_restart_services']:
        restarted[service] = __salt__['service.restart'](service)
    return {'comment': 'Updated from {0} to {1}'.format(oldversion, version),
            'restarted': restarted}


def sync_modules(env=None):
    '''
    Sync the modules from the _modules directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _modules directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_modules
    '''
    return _sync('modules', env)


def sync_states(env=None):
    '''
    Sync the states from the _states directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _states directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_states
    '''
    return _sync('states', env)


def sync_grains(env=None):
    '''
    Sync the grains from the _grains directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _grains directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_grains
    '''
    return _sync('grains', env)


def sync_renderers(env=None):
    '''
    Sync the renderers from the _renderers directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _renderers directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_renderers
    '''
    return _sync('renderers', env)


def sync_returners(env=None):
    '''
    Sync the returners from the _returners directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _returners directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_returners
    '''
    return _sync('returners', env)


def sync_outputters(env=None):
    '''
    Sync the outputters from the _outputters directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _outputters directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_outputters
    '''
    return _sync('outputters', env)


def sync_all(env=None):
    '''
    Sync down all of the dynamic modules from the file server for a specific
    environment

    CLI Example::

        salt '*' saltutil.sync_all
    '''
    logging.debug("Syncing all")
    ret = []
    ret.append(sync_modules(env))
    ret.append(sync_states(env))
    ret.append(sync_grains(env))
    ret.append(sync_renderers(env))
    ret.append(sync_returners(env))
    ret.append(sync_outputters(env))
    return ret


def refresh_pillar():
    '''
    Queue the minion to refresh the pillar data.

    CLI Example::

        salt '*' saltutil.refresh_pillar
    '''
    mod_file = os.path.join(__opts__['cachedir'], 'module_refresh')
    try:
        with salt.utils.fopen(mod_file, 'a+') as ofile:
            ofile.write('pillar')
        return True
    except IOError:
        return False


def is_running(fun):
    '''
    If the named function is running return the data associated with it/them.
    The argument can be a glob

    CLI Example::

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

    CLI Example::

        salt '*' saltutil.running
    '''
    procs = __salt__['status.procs']()
    ret = []
    serial = salt.payload.Serial(__opts__)
    pid = os.getpid()
    proc_dir = os.path.join(__opts__['cachedir'], 'proc')
    if not os.path.isdir(proc_dir):
        return []
    for fn_ in os.listdir(proc_dir):
        path = os.path.join(proc_dir, fn_)
        with salt.utils.fopen(path, 'rb') as fp_:
            data = serial.loads(fp_.read())
        if not isinstance(data, dict):
            # Invalid serial object
            continue
        if not procs.get(str(data['pid'])):
            # The process is no longer running, clear out the file and
            # continue
            os.remove(path)
            continue
        if data.get('pid') == pid:
            continue
        ret.append(data)
    return ret


def find_job(jid):
    '''
    Return the data for a specific job id

    CLI Example::

        salt '*' saltutil.find_job <job id>
    '''
    for data in running():
        if data['jid'] == jid:
            return data
    return {}


def signal_job(jid, sig):
    '''
    Sends a signal to the named salt job's process

    CLI Example::

        salt '*' saltutil.signal_job <job id> 15
    '''
    for data in running():
        if data['jid'] == jid:
            try:
                os.kill(int(data['pid']), sig)
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

    CLI Example::

        salt '*' saltutil.term_job <job id>
    '''
    return signal_job(jid, signal.SIGTERM)


def kill_job(jid):
    '''
    Sends a kill signal (SIGKILL 9) to the named salt job's process

    CLI Example::

        salt '*' saltutil.kill_job <job id>
    '''
    return signal_job(jid, signal.SIGKILL)
