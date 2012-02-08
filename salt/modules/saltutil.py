'''
The Saltutil module is used to manage the state of the salt minion itself. It is
used to manage minion modules as well as automate updates to the salt minion
'''

# Import Python libs
import os
import hashlib
import shutil
import signal
import logging

# Import Salt libs
import salt.payload

log = logging.getLogger(__name__)

def _sync(form, env):
    '''
    Sync the given directory in the given environment
    '''
    if isinstance(env, str):
        env = env.split(',')
    ret = []
    remote = set()
    source = os.path.join('salt://_{0}'.format(form))
    mod_dir = os.path.join(__opts__['extension_modules'], '{0}'.format(form))
    if not os.path.isdir(mod_dir):
        os.makedirs(mod_dir)
    cache = []
    for sub_env in env:
        cache.extend(__salt__['cp.cache_dir'](source, sub_env))
    for fn_ in cache:
        remote.add(os.path.basename(fn_))
        dest = os.path.join(mod_dir,
                os.path.basename(fn_)
                )
        if os.path.isfile(dest):
            # The file is present, if the sum differes replace it
            srch = hashlib.md5(open(fn_, 'r').read()).hexdigest()
            dsth = hashlib.md5(open(dest, 'r').read()).hexdigest()
            if srch != dsth:
                # The downloaded file differes, replace!
                shutil.copyfile(fn_, dest)
                ret.append('{0}.{1}'.format(form, os.path.basename(fn_)))
        else:
            shutil.copyfile(fn_, dest)
            ret.append('{0}.{1}'.format(form, os.path.basename(fn_)))
    if ret:
        open(os.path.join(__opts__['cachedir'], 'module_refresh'), 'w+').write('')
    if __opts__.get('clean_dynamic_modules', True):
        current = set(os.listdir(mod_dir))
        for fn_ in current.difference(remote):
            full = os.path.join(mod_dir, fn_)
            if os.path.isfile(full):
                os.remove(full)
    return ret


def sync_modules(env='base'):
    '''
    Sync the modules from the _modules directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _modules directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_modules
    '''
    return _sync('modules', env)


def sync_states(env='base'):
    '''
    Sync the states from the _states directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _states directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_states
    '''
    return _sync('states', env)


def sync_grains(env='base'):
    '''
    Sync the grains from the _grains directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _grains directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_grains
    '''
    return _sync('grains', env)


def sync_renderers(env='base'):
    '''
    Sync the renderers from the _renderers directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _renderers directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_renderers
    '''
    return _sync('renderers', env)


def sync_returners(env='base'):
    '''
    Sync the returners from the _returners directory on the salt master file
    server. This function is environment aware, pass the desired environment
    to grab the contents of the _returners directory, base is the default
    environment.

    CLI Example::

        salt '*' saltutil.sync_returners
    '''
    return _sync('returners', env)


def sync_all(env='base'):
    '''
    Sync down all of the dynamic modules from the file server for a specific
    environment

    CLI Example::

        salt '*' saltutil.sync_all
    '''
    ret = []
    ret.append(sync_modules(env))
    ret.append(sync_states(env))
    ret.append(sync_grains(env))
    ret.append(sync_renderers(env))
    ret.append(sync_returners(env))
    return ret


def running():
    '''
    Return the data on all running processes salt on the minion

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
        data = serial.loads(open(path, 'rb').read())
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
    Sends a termination signal (SIGTERM 15) to the named salt job's process

    CLI Example::

        salt '*' saltutil.kill_job <job id>
    '''
    return signal_job(jid, signal.SIGKILL)
