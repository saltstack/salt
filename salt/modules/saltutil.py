# -*- coding: utf-8 -*-
'''
The Saltutil module is used to manage the state of the salt minion itself. It
is used to manage minion modules as well as automate updates to the salt
minion.

:depends:   - esky Python module for update functionality
'''
from __future__ import absolute_import

# Import python libs
import copy
import fnmatch
import logging
import os
import signal
import sys

# Import 3rd-party libs
# pylint: disable=import-error
try:
    import esky
    from esky import EskyVersionError
    HAS_ESKY = True
except ImportError:
    HAS_ESKY = False
# pylint: disable=no-name-in-module
from salt.ext import six
from salt.ext.six.moves.urllib.error import URLError
# pylint: enable=import-error,no-name-in-module

# Fix a nasty bug with Win32 Python not supporting all of the standard signals
try:
    salt_SIGKILL = signal.SIGKILL
except AttributeError:
    salt_SIGKILL = signal.SIGTERM

# Import salt libs
import salt
import salt.config
import salt.client
import salt.client.ssh.client
import salt.payload
import salt.runner
import salt.state
import salt.transport
import salt.utils
import salt.utils.args
import salt.utils.event
import salt.utils.extmods
import salt.utils.minion
import salt.utils.process
import salt.utils.url
import salt.wheel

HAS_PSUTIL = True
try:
    import salt.utils.psutil_compat
except ImportError:
    HAS_PSUTIL = False

from salt.exceptions import (
    SaltReqTimeoutError, SaltRenderError, CommandExecutionError, SaltInvocationError
)

__proxyenabled__ = ['*']

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
                envs = list(st_.top_matches(top).keys()) or 'base'
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
    if isinstance(saltenv, six.string_types):
        saltenv = saltenv.split(',')
    ret, touched = salt.utils.extmods.sync(__opts__, form, saltenv=saltenv)
    # Dest mod_dir is touched? trigger reload if requested
    if touched:
        mod_file = os.path.join(__opts__['cachedir'], 'module_refresh')
        with salt.utils.fopen(mod_file, 'a+') as ofile:
            ofile.write('')
    if form == 'grains' and \
       __opts__.get('grains_cache') and \
       os.path.isfile(os.path.join(__opts__['cachedir'], 'grains.cache.p')):
        try:
            os.remove(os.path.join(__opts__['cachedir'], 'grains.cache.p'))
        except OSError:
            log.error('Could not remove grains cache!')
    return ret


def update(version=None):
    '''
    Update the salt minion from the URL defined in opts['update_url']
    SaltStack, Inc provides the latest builds here:
    update_url: https://repo.saltstack.com/windows/

    Be aware that as of 2014-8-11 there's a bug in esky such that only the
    latest version available in the update_url can be downloaded and installed.

    This feature requires the minion to be running a bdist_esky build.

    The version number is optional and will default to the most recent version
    available at opts['update_url'].

    Returns details about the transaction upon completion.

    CLI Examples:

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


def sync_beacons(saltenv=None, refresh=True):
    '''
    .. versionadded:: 2015.5.1

    Sync beacons from ``salt://_beacons`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available beacons on the minion. This refresh
        will be performed even if no new beacons are synced. Set to ``False``
        to prevent this refresh.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_beacons
        salt '*' saltutil.sync_beacons saltenv=dev
        salt '*' saltutil.sync_beacons saltenv=base,dev
    '''
    ret = _sync('beacons', saltenv)
    if refresh:
        refresh_beacons()
    return ret


def sync_sdb(saltenv=None):
    '''
    .. versionadded:: 2015.5.8,2015.8.3

    Sync sdb modules from ``salt://_sdb`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : False
        This argument has no affect and is included for consistency with the
        other sync functions.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_sdb
        salt '*' saltutil.sync_sdb saltenv=dev
        salt '*' saltutil.sync_sdb saltenv=base,dev
    '''
    ret = _sync('sdb', saltenv)
    return ret


def sync_modules(saltenv=None, refresh=True):
    '''
    .. versionadded:: 0.10.0

    Sync execution modules from ``salt://_modules`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new execution modules are
        synced. Set to ``False`` to prevent this refresh.

    .. important::

        If this function is executed using a :py:func:`module.run
        <salt.states.module.run>` state, the SLS file will not have access to
        newly synced execution modules unless a ``refresh`` argument is
        added to the state, like so:

        .. code-block:: yaml

            load_my_custom_module:
              module.run:
                - name: saltutil.sync_modules
                - refresh: True

        See :ref:`here <reloading-modules>` for a more detailed explanation of
        why this is necessary.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.sync_modules
        salt '*' saltutil.sync_modules saltenv=dev
        salt '*' saltutil.sync_modules saltenv=base,dev
    '''
    ret = _sync('modules', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_states(saltenv=None, refresh=True):
    '''
    .. versionadded:: 0.10.0

    Sync state modules from ``salt://_states`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available states on the minion. This refresh
        will be performed even if no new state modules are synced. Set to
        ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_states
        salt '*' saltutil.sync_states saltenv=dev
        salt '*' saltutil.sync_states saltenv=base,dev
    '''
    ret = _sync('states', saltenv)
    if refresh:
        refresh_modules()
    return ret


def refresh_grains(**kwargs):
    '''
    .. versionadded:: 2016.3.6,2016.11.4,Nitrogen

    Refresh the minion's grains without syncing custom grains modules from
    ``salt://_grains``.

    .. note::
        The available execution modules will be reloaded as part of this
        proceess, as grains can affect which modules are available.

    refresh_pillar : True
        Set to ``False`` to keep pillar data from being refreshed.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.refresh_grains
    '''
    kwargs = salt.utils.clean_kwargs(**kwargs)
    _refresh_pillar = kwargs.pop('refresh_pillar', True)
    if kwargs:
        salt.utils.invalid_kwargs(kwargs)
    # Modules and pillar need to be refreshed in case grains changes affected
    # them, and the module refresh process reloads the grains and assigns the
    # newly-reloaded grains to each execution module's __grains__ dunder.
    refresh_modules()
    if _refresh_pillar:
        refresh_pillar()
    return True


def sync_grains(saltenv=None, refresh=True):
    '''
    .. versionadded:: 0.10.0

    Sync grains modules from ``salt://_grains`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules and recompile
        pillar data for the minion. This refresh will be performed even if no
        new grains modules are synced. Set to ``False`` to prevent this
        refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_grains
        salt '*' saltutil.sync_grains saltenv=dev
        salt '*' saltutil.sync_grains saltenv=base,dev
    '''
    ret = _sync('grains', saltenv)
    if refresh:
        refresh_modules()
        refresh_pillar()
    return ret


def sync_renderers(saltenv=None, refresh=True):
    '''
    .. versionadded:: 0.10.0

    Sync renderers from ``salt://_renderers`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new renderers are synced.
        Set to ``False`` to prevent this refresh. Set to ``False`` to prevent
        this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_renderers
        salt '*' saltutil.sync_renderers saltenv=dev
        salt '*' saltutil.sync_renderers saltenv=base,dev
    '''
    ret = _sync('renderers', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_returners(saltenv=None, refresh=True):
    '''
    .. versionadded:: 0.10.0

    Sync beacons from ``salt://_returners`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new returners are synced. Set
        to ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_returners
        salt '*' saltutil.sync_returners saltenv=dev
    '''
    ret = _sync('returners', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_proxymodules(saltenv=None, refresh=False):
    '''
    .. versionadded:: 2015.8.2

    Sync proxy modules from ``salt://_proxy`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new proxy modules are synced.
        Set to ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_proxymodules
        salt '*' saltutil.sync_proxymodules saltenv=dev
        salt '*' saltutil.sync_proxymodules saltenv=base,dev
    '''
    ret = _sync('proxy', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_engines(saltenv=None, refresh=False):
    '''
    .. versionadded:: 2016.3.0

    Sync engine modules from ``salt://_engines`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new engine modules are synced.
        Set to ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_engines
        salt '*' saltutil.sync_engines saltenv=base,dev
    '''
    ret = _sync('engines', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_output(saltenv=None, refresh=True):
    '''
    Sync outputters from ``salt://_output`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new outputters are synced.
        Set to ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_output
        salt '*' saltutil.sync_output saltenv=dev
        salt '*' saltutil.sync_output saltenv=base,dev
    '''
    ret = _sync('output', saltenv)
    if refresh:
        refresh_modules()
    return ret

sync_outputters = salt.utils.alias_function(sync_output, 'sync_outputters')


def sync_utils(saltenv=None, refresh=True):
    '''
    .. versionadded:: 2014.7.0

    Sync utility modules from ``salt://_utils`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new utility modules are
        synced. Set to ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_utils
        salt '*' saltutil.sync_utils saltenv=dev
        salt '*' saltutil.sync_utils saltenv=base,dev
    '''
    ret = _sync('utils', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_log_handlers(saltenv=None, refresh=True):
    '''
    .. versionadded:: 2015.8.0

    Sync log handlers from ``salt://_log_handlers`` to the minion

    saltenv : base
        The fileserver environment from which to sync. To sync from more than
        one environment, pass a comma-separated list.

    refresh : True
        If ``True``, refresh the available execution modules on the minion.
        This refresh will be performed even if no new log handlers are synced.
        Set to ``False`` to prevent this refresh.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_log_handlers
        salt '*' saltutil.sync_log_handlers saltenv=dev
        salt '*' saltutil.sync_log_handlers saltenv=base,dev
    '''
    ret = _sync('log_handlers', saltenv)
    if refresh:
        refresh_modules()
    return ret


def sync_pillar(saltenv=None, refresh=True):
    '''
    .. versionadded:: 2015.8.11,2016.3.2

    Sync pillar modules from the ``salt://_pillar`` directory on the Salt
    fileserver. This function is environment-aware, pass the desired
    environment to grab the contents of the ``_pillar`` directory from that
    environment. The default environment, if none is specified,  is ``base``.

    refresh : True
        Also refresh the execution modules available to the minion, and refresh
        pillar data.

    .. note::
        This function will raise an error if executed on a traditional (i.e.
        not masterless) minion

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_pillar
        salt '*' saltutil.sync_pillar saltenv=dev
    '''
    if __opts__['file_client'] != 'local':
        raise CommandExecutionError(
            'Pillar modules can only be synced to masterless minions'
        )
    ret = _sync('pillar', saltenv)
    if refresh:
        refresh_modules()
        refresh_pillar()
    return ret


def sync_all(saltenv=None, refresh=True):
    '''
    .. versionchanged:: 2015.8.11,2016.3.2
        On masterless minions, pillar modules are now synced, and refreshed
        when ``refresh`` is set to ``True``.

    Sync down all of the dynamic modules from the file server for a specific
    environment. This function synchronizes custom modules, states, beacons,
    grains, returners, output modules, renderers, and utils.

    refresh : True
        Also refresh the execution modules and recompile pillar data available
        to the minion. This refresh will be performed even if no new dynamic
        modules are synced. Set to ``False`` to prevent this refresh.

    .. important::

        If this function is executed using a :py:func:`module.run
        <salt.states.module.run>` state, the SLS file will not have access to
        newly synced execution modules unless a ``refresh`` argument is
        added to the state, like so:

        .. code-block:: yaml

            load_my_custom_module:
              module.run:
                - name: saltutil.sync_all
                - refresh: True

        See :ref:`here <reloading-modules>` for a more detailed explanation of
        why this is necessary.

    CLI Examples:

    .. code-block:: bash

        salt '*' saltutil.sync_all
        salt '*' saltutil.sync_all saltenv=dev
        salt '*' saltutil.sync_all saltenv=base,dev
    '''
    log.debug('Syncing all')
    ret = {}
    ret['beacons'] = sync_beacons(saltenv, False)
    ret['modules'] = sync_modules(saltenv, False)
    ret['states'] = sync_states(saltenv, False)
    ret['sdb'] = sync_sdb(saltenv)
    ret['grains'] = sync_grains(saltenv, False)
    ret['renderers'] = sync_renderers(saltenv, False)
    ret['returners'] = sync_returners(saltenv, False)
    ret['output'] = sync_output(saltenv, False)
    ret['utils'] = sync_utils(saltenv, False)
    ret['log_handlers'] = sync_log_handlers(saltenv, False)
    ret['proxymodules'] = sync_proxymodules(saltenv, False)
    ret['engines'] = sync_engines(saltenv, False)
    if __opts__['file_client'] == 'local':
        ret['pillar'] = sync_pillar(saltenv, False)
    if refresh:
        refresh_modules()
        refresh_pillar()
    return ret


def refresh_beacons():
    '''
    Signal the minion to refresh the beacons.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_beacons
    '''
    try:
        ret = __salt__['event.fire']({}, 'beacons_refresh')
    except KeyError:
        log.error('Event module not available. Module refresh failed.')
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret


def refresh_pillar():
    '''
    Signal the minion to refresh the pillar data.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_pillar
    '''
    try:
        ret = __salt__['event.fire']({}, 'pillar_refresh')
    except KeyError:
        log.error('Event module not available. Module refresh failed.')
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret

pillar_refresh = salt.utils.alias_function(refresh_pillar, 'pillar_refresh')


def refresh_modules(async=True):
    '''
    Signal the minion to refresh the module and grain data

    The default is to refresh module asynchronously. To block
    until the module refresh is complete, set the 'async' flag
    to False.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.refresh_modules
    '''
    try:
        if async:
            #  If we're going to block, first setup a listener
            ret = __salt__['event.fire']({}, 'module_refresh')
        else:
            eventer = salt.utils.event.get_event('minion', opts=__opts__, listen=True)
            ret = __salt__['event.fire']({'notify': True}, 'module_refresh')
            # Wait for the finish event to fire
            log.trace('refresh_modules waiting for module refresh to complete')
            # Blocks until we hear this event or until the timeout expires
            eventer.get_event(tag='/salt/minion/minion_mod_complete', wait=30)
    except KeyError:
        log.error('Event module not available. Module refresh failed.')
        ret = False  # Effectively a no-op, since we can't really return without an event system
    return ret


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
    Return the data for a specific job id that is currently running.

    jid
        The job id to search for and return data.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.find_job <job id>

    Note that the find_job function only returns job information when the job is still running. If
    the job is currently running, the output looks something like this:

    .. code-block:: bash

        # salt my-minion saltutil.find_job 20160503150049487736
        my-minion:
            ----------
            arg:
                - 30
            fun:
                test.sleep
            jid:
                20160503150049487736
            pid:
                9601
            ret:
            tgt:
                my-minion
            tgt_type:
                glob
            user:
                root

    If the job has already completed, the job cannot be found and therefore the function returns
    an empty dictionary, which looks like this on the CLI:

    .. code-block:: bash

        # salt my-minion saltutil.find_job 20160503150049487736
        my-minion:
            ----------
    '''
    for data in running():
        if data['jid'] == jid:
            return data
    return {}


def find_cached_job(jid):
    '''
    Return the data for a specific cached job id. Note this only works if
    cache_jobs has previously been set to True on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.find_cached_job <job id>
    '''
    serial = salt.payload.Serial(__opts__)
    proc_dir = os.path.join(__opts__['cachedir'], 'minion_jobs')
    job_dir = os.path.join(proc_dir, str(jid))
    if not os.path.isdir(job_dir):
        if not __opts__.get('cache_jobs'):
            return ('Local jobs cache directory not found; you may need to'
                    ' enable cache_jobs on this minion')
        else:
            return 'Local jobs cache directory {0} not found'.format(job_dir)
    path = os.path.join(job_dir, 'return.p')
    with salt.utils.fopen(path, 'rb') as fp_:
        buf = fp_.read()
        fp_.close()
        if buf:
            try:
                data = serial.loads(buf)
            except NameError:
                # msgpack error in salt-ssh
                return
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
    if HAS_PSUTIL is False:
        log.warning('saltutil.signal job called, but psutil is not installed. '
                    'Install psutil to ensure more reliable and accurate PID '
                    'management.')
    for data in running():
        if data['jid'] == jid:
            try:
                if HAS_PSUTIL:
                    for proc in salt.utils.psutil_compat.Process(pid=data['pid']).children(recursive=True):
                        proc.send_signal(sig)
                os.kill(int(data['pid']), sig)
                if HAS_PSUTIL is False and 'child_pids' in data:
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


def term_all_jobs():
    '''
    Sends a termination signal (SIGTERM 15) to all currently running jobs

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.term_all_jobs
    '''
    ret = []
    for data in running():
        ret.append(signal_job(data['jid'], signal.SIGTERM))
    return ret


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


def kill_all_jobs():
    '''
    Sends a kill signal (SIGKILL 9) to all currently running jobs

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.kill_all_jobs
    '''
    # Some OS's (Win32) don't have SIGKILL, so use salt_SIGKILL which is set to
    # an appropriate value for the operating system this is running on.
    ret = []
    for data in running():
        ret.append(signal_job(data['jid'], salt_SIGKILL))
    return ret


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
    # TODO: move this into a channel function? Or auth?
    # create a channel again, this will force the key regen
    channel = salt.transport.Channel.factory(__opts__)


def revoke_auth(preserve_minion_cache=False):
    '''
    The minion sends a request to the master to revoke its own key.
    Note that the minion session will be revoked and the minion may
    not be able to return the result of this command back to the master.

    If the 'preserve_minion_cache' flag is set to True, the master
    cache for this minion will not be removed.

    CLI Example:

    .. code-block:: bash

        salt '*' saltutil.revoke_auth
    '''
    masters = list()
    ret = True
    if 'master_uri_list' in __opts__:
        for master_uri in __opts__['master_uri_list']:
            masters.append(master_uri)
    else:
        masters.append(__opts__['master_uri'])

    for master in masters:
        channel = salt.transport.Channel.factory(__opts__, master_uri=master)
        tok = channel.auth.gen_token('salt')
        load = {'cmd': 'revoke_auth',
                'id': __opts__['id'],
                'tok': tok,
                'preserve_minion_cache': preserve_minion_cache}
        try:
            channel.send(load)
        except SaltReqTimeoutError:
            ret = False
    return ret


def _get_ssh_or_api_client(cfgfile, ssh=False):
    if ssh:
        client = salt.client.ssh.client.SSHClient(cfgfile)
    else:
        client = salt.client.get_local_client(cfgfile)
    return client


def _exec(client, tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs):
    fcn_ret = {}
    seen = 0
    if 'batch' in kwargs:
        _cmd = client.cmd_batch
        cmd_kwargs = {
            'tgt': tgt, 'fun': fun, 'arg': arg, 'expr_form': expr_form,
            'ret': ret, 'kwarg': kwarg, 'batch': kwargs['batch'],
        }
        del kwargs['batch']
    else:
        _cmd = client.cmd_iter
        cmd_kwargs = {
            'tgt': tgt, 'fun': fun, 'arg': arg, 'timeout': timeout,
            'expr_form': expr_form, 'ret': ret, 'kwarg': kwarg,
        }
    cmd_kwargs.update(kwargs)
    for ret_comp in _cmd(**cmd_kwargs):
        fcn_ret.update(ret_comp)
        seen += 1
        # fcn_ret can be empty, so we cannot len the whole return dict
        if expr_form == 'list' and len(tgt) == seen:
            # do not wait for timeout when explicit list matching
            # and all results are there
            break
    return fcn_ret


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
    fcn_ret = _exec(
        client, tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs)
    # if return is empty, we may have not used the right conf,
    # try with the 'minion relative master configuration counter part
    # if available
    master_cfgfile = '{0}master'.format(cfgfile[:-6])  # remove 'minion'
    if (
        not fcn_ret
        and cfgfile.endswith('{0}{1}'.format(os.path.sep, 'minion'))
        and os.path.exists(master_cfgfile)
    ):
        client = _get_ssh_or_api_client(master_cfgfile, ssh)
        fcn_ret = _exec(
            client, tgt, fun, arg, timeout, expr_form, ret, kwarg, **kwargs)

    if 'batch' in kwargs:
        old_ret, fcn_ret = fcn_ret, {}
        for key, value in old_ret.items():
            fcn_ret[key] = {
                'out': value.get('out', 'highstate') if isinstance(value, dict) else 'highstate',
                'ret': value,
            }

    return fcn_ret


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

        salt '*' saltutil.cmd_iter
    '''
    if ssh:
        client = salt.client.ssh.client.SSHClient(__opts__['conf_file'])
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


def runner(name, **kwargs):
    '''
    Execute a runner function. This function must be run on the master,
    either by targeting a minion running on a master or by using
    salt-call on a master.

    .. versionadded:: 2014.7.0

    name
        The name of the function to run

    kwargs
        Any keyword arguments to pass to the runner function

    CLI Example:

    In this example, assume that `master_minion` is a minion running
    on a master.

    .. code-block:: bash

        salt master_minion saltutil.runner jobs.list_jobs
    '''
    jid = kwargs.pop('__orchestration_jid__', None)
    saltenv = kwargs.pop('__env__', 'base')
    full_return = kwargs.pop('full_return', False)
    kwargs = salt.utils.clean_kwargs(**kwargs)

    if 'master_job_cache' not in __opts__:
        master_config = os.path.join(os.path.dirname(__opts__['conf_file']),
                                     'master')
        master_opts = salt.config.master_config(master_config)
        rclient = salt.runner.RunnerClient(master_opts)
    else:
        rclient = salt.runner.RunnerClient(__opts__)

    if name in rclient.functions:
        aspec = salt.utils.args.get_function_argspec(rclient.functions[name])
        if 'saltenv' in aspec.args:
            kwargs['saltenv'] = saltenv

    if jid:
        salt.utils.event.fire_args(
            __opts__,
            jid,
            {'type': 'runner', 'name': name, 'args': kwargs},
            prefix='run'
        )

    return rclient.cmd(name,
                       kwarg=kwargs,
                       print_event=False,
                       full_return=full_return)


def wheel(name, *args, **kwargs):
    '''
    Execute a wheel module and function. This function must be run against a
    minion that is local to the master.

    .. versionadded:: 2014.7.0

    name
        The name of the function to run

    args
        Any positional arguments to pass to the wheel function. A common example
        of this would be the ``match`` arg needed for key functions.

        .. versionadded:: v2015.8.11

    kwargs
        Any keyword arguments to pass to the wheel function

    CLI Example:

    .. code-block:: bash

        salt my-local-minion saltutil.wheel key.accept jerry
        salt my-local-minion saltutil.wheel minions.connected

    .. note::

        Since this function must be run against a minion that is running locally
        on the master in order to get accurate returns, if this function is run
        against minions that are not local to the master, "empty" returns are
        expected. The remote minion does not have access to wheel functions and
        their return data.

    '''
    jid = kwargs.pop('__orchestration_jid__', None)
    saltenv = kwargs.pop('__env__', 'base')

    if __opts__['__role'] == 'minion':
        master_config = os.path.join(os.path.dirname(__opts__['conf_file']),
                                     'master')
        master_opts = salt.config.client_config(master_config)
        wheel_client = salt.wheel.WheelClient(master_opts)
    else:
        wheel_client = salt.wheel.WheelClient(__opts__)

    # The WheelClient cmd needs args, kwargs, and pub_data separated out from
    # the "normal" kwargs structure, which at this point contains __pub_x keys.
    pub_data = {}
    valid_kwargs = {}
    for key, val in six.iteritems(kwargs):
        if key.startswith('__'):
            pub_data[key] = val
        else:
            valid_kwargs[key] = val

    try:
        if name in wheel_client.functions:
            aspec = salt.utils.args.get_function_argspec(
                wheel_client.functions[name]
            )
            if 'saltenv' in aspec.args:
                valid_kwargs['saltenv'] = saltenv

        if jid:
            salt.utils.event.fire_args(
                __opts__,
                jid,
                {'type': 'wheel', 'name': name, 'args': valid_kwargs},
                prefix='run'
            )

        ret = wheel_client.cmd(name,
                               arg=args,
                               pub_data=pub_data,
                               kwarg=valid_kwargs,
                               print_event=False,
                               full_return=True)
    except SaltInvocationError:
        raise CommandExecutionError(
            'This command can only be executed on a minion that is located on '
            'the master.'
        )

    return ret


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
