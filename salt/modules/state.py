# -*- coding: utf-8 -*-
'''
Control the state system on the minion.

State Caching
-------------

When a highstate is called, the minion automatically caches a copy of the last
high data. If you then run a highstate with cache=True it will use that cached
highdata and won't hit the fileserver except for ``salt://`` links in the
states themselves.
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import os
import shutil
import sys
import tarfile
import tempfile
import time

# Import salt libs
import salt.config
import salt.payload
import salt.state
import salt.utils.args
import salt.utils.data
import salt.utils.event
import salt.utils.files
import salt.utils.functools
import salt.utils.hashutils
import salt.utils.jid
import salt.utils.json
import salt.utils.platform
import salt.utils.state
import salt.utils.stringutils
import salt.utils.url
import salt.utils.versions
import salt.defaults.exitcodes
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.runners.state import orchestrate as _orchestrate
from salt.utils.odict import OrderedDict

# Import 3rd-party libs
from salt.ext import six
import msgpack

__proxyenabled__ = ['*']

__outputter__ = {
    'sls': 'highstate',
    'sls_id': 'highstate',
    'pkg': 'highstate',
    'top': 'highstate',
    'single': 'highstate',
    'highstate': 'highstate',
    'template': 'highstate',
    'template_str': 'highstate',
    'apply_': 'highstate',
    'request': 'highstate',
    'check_request': 'highstate',
    'run_request': 'highstate',
}

__func_alias__ = {
    'apply_': 'apply'
}
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'state'


def __virtual__():
    '''
    Set the virtualname
    '''
    # Update global namespace with functions that are cloned in this module
    global _orchestrate
    _orchestrate = salt.utils.functools.namespaced_function(_orchestrate, globals())

    return __virtualname__


def _filter_running(runnings):
    '''
    Filter out the result: True + no changes data
    '''
    ret = dict((tag, value) for tag, value in six.iteritems(runnings)
               if not value['result'] or value['changes'])
    return ret


def _set_retcode(ret, highstate=None):
    '''
    Set the return code based on the data back from the state system
    '''

    # Set default retcode to 0
    __context__['retcode'] = salt.defaults.exitcodes.EX_OK

    if isinstance(ret, list):
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return
    if not __utils__['state.check_result'](ret, highstate=highstate):
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_FAILURE


def _get_pillar_errors(kwargs, pillar=None):
    '''
    Checks all pillars (external and internal) for errors.
    Return an error message, if anywhere or None.

    :param kwargs: dictionary of options
    :param pillar: external pillar
    :return: None or an error message
    '''
    return None if kwargs.get('force') else (pillar or {}).get('_errors', __pillar__.get('_errors')) or None


def _wait(jid):
    '''
    Wait for all previously started state jobs to finish running
    '''
    if jid is None:
        jid = salt.utils.jid.gen_jid(__opts__)
    states = _prior_running_states(jid)
    while states:
        time.sleep(1)
        states = _prior_running_states(jid)


def _snapper_pre(opts, jid):
    '''
    Create a snapper pre snapshot
    '''
    snapper_pre = None
    try:
        if not opts['test'] and __opts__.get('snapper_states'):
            # Run the snapper pre snapshot
            snapper_pre = __salt__['snapper.create_snapshot'](
                    config=__opts__.get('snapper_states_config', 'root'),
                    snapshot_type='pre',
                    description='Salt State run for jid {0}'.format(jid),
                    __pub_jid=jid)
    except Exception:
        log.error('Failed to create snapper pre snapshot for jid: %s', jid)
    return snapper_pre


def _snapper_post(opts, jid, pre_num):
    '''
    Create the post states snapshot
    '''
    try:
        if not opts['test'] and __opts__.get('snapper_states') and pre_num:
            # Run the snapper pre snapshot
            __salt__['snapper.create_snapshot'](
                    config=__opts__.get('snapper_states_config', 'root'),
                    snapshot_type='post',
                    pre_number=pre_num,
                    description='Salt State run for jid {0}'.format(jid),
                    __pub_jid=jid)
    except Exception:
        log.error('Failed to create snapper pre snapshot for jid: %s', jid)


def _get_pause(jid, state_id=None):
    '''
    Return the pause information for a given jid
    '''
    pause_dir = os.path.join(__opts__['cachedir'], 'state_pause')
    pause_path = os.path.join(pause_dir, jid)
    if not os.path.exists(pause_dir):
        try:
            os.makedirs(pause_dir)
        except OSError:
            # File created in the gap
            pass
    data = {}
    if state_id is not None:
        if state_id not in data:
            data[state_id] = {}
    if os.path.exists(pause_path):
        with salt.utils.files.fopen(pause_path, 'rb') as fp_:
            data = msgpack.loads(fp_.read())
    return data, pause_path


def get_pauses(jid=None):
    '''
    Get a report on all of the currently paused state runs and pause
    run settings.
    Optionally send in a jid if you only desire to see a single pause
    data set.
    '''
    ret = {}
    active = __salt__['saltutil.is_running']('state.*')
    pause_dir = os.path.join(__opts__['cachedir'], 'state_pause')
    if not os.path.exists(pause_dir):
        return ret
    if jid is None:
        jids = os.listdir(pause_dir)
    elif isinstance(jid, list):
        jids = salt.utils.data.stringify(jid)
    else:
        jids = [six.text_type(jid)]
    for scan_jid in jids:
        is_active = False
        for active_data in active:
            if active_data['jid'] == scan_jid:
                is_active = True
        if not is_active:
            try:
                pause_path = os.path.join(pause_dir, scan_jid)
                os.remove(pause_path)
            except OSError:
                # Already gone
                pass
            continue
        data, pause_path = _get_pause(scan_jid)
        ret[scan_jid] = data
    return ret


def soft_kill(jid, state_id=None):
    '''
    Set up a state run to die before executing the given state id,
    this instructs a running state to safely exit at a given
    state id. This needs to pass in the jid of the running state.
    If a state_id is not passed then the jid referenced will be safely exited
    at the beginning of the next state run.

    The given state id is the id got a given state execution, so given a state
    that looks like this:

    .. code-block:: yaml

        vim:
          pkg.installed: []

    The state_id to pass to `soft_kill` is `vim`

    CLI Examples:

    .. code-block:: bash

        salt '*' state.soft_kill 20171130110407769519
        salt '*' state.soft_kill 20171130110407769519 vim
    '''
    jid = six.text_type(jid)
    if state_id is None:
        state_id = '__all__'
    data, pause_path = _get_pause(jid, state_id)
    data[state_id]['kill'] = True
    with salt.utils.files.fopen(pause_path, 'wb') as fp_:
        fp_.write(msgpack.dumps(data))


def pause(jid, state_id=None, duration=None):
    '''
    Set up a state id pause, this instructs a running state to pause at a given
    state id. This needs to pass in the jid of the running state and can
    optionally pass in a duration in seconds. If a state_id is not passed then
    the jid referenced will be paused at the beginning of the next state run.

    The given state id is the id got a given state execution, so given a state
    that looks like this:

    .. code-block:: yaml

        vim:
          pkg.installed: []

    The state_id to pass to `pause` is `vim`

    CLI Examples:

    .. code-block:: bash

        salt '*' state.pause 20171130110407769519
        salt '*' state.pause 20171130110407769519 vim
        salt '*' state.pause 20171130110407769519 vim 20
    '''
    jid = six.text_type(jid)
    if state_id is None:
        state_id = '__all__'
    data, pause_path = _get_pause(jid, state_id)
    if duration:
        data[state_id]['duration'] = int(duration)
    with salt.utils.files.fopen(pause_path, 'wb') as fp_:
        fp_.write(msgpack.dumps(data))


def resume(jid, state_id=None):
    '''
    Remove a pause from a jid, allowing it to continue. If the state_id is
    not specified then the a general pause will be resumed.

    The given state_id is the id got a given state execution, so given a state
    that looks like this:

    .. code-block:: yaml

        vim:
          pkg.installed: []

    The state_id to pass to `rm_pause` is `vim`

    CLI Examples:

    .. code-block:: bash

        salt '*' state.resume 20171130110407769519
        salt '*' state.resume 20171130110407769519 vim
    '''
    jid = six.text_type(jid)
    if state_id is None:
        state_id = '__all__'
    data, pause_path = _get_pause(jid, state_id)
    if state_id in data:
        data.pop(state_id)
    if state_id == '__all__':
        data = {}
    with salt.utils.files.fopen(pause_path, 'wb') as fp_:
        fp_.write(msgpack.dumps(data))


def orchestrate(mods,
                saltenv='base',
                test=None,
                exclude=None,
                pillar=None,
                pillarenv=None):
    '''
    .. versionadded:: 2016.11.0

    Execute the orchestrate runner from a masterless minion.

    .. seealso:: More Orchestrate documentation

        * :ref:`Full Orchestrate Tutorial <orchestrate-runner>`
        * :py:mod:`Docs for the ``salt`` state module <salt.states.saltmod>`

    CLI Examples:

    .. code-block:: bash

        salt-call --local state.orchestrate webserver
        salt-call --local state.orchestrate webserver saltenv=dev test=True
        salt-call --local state.orchestrate webserver saltenv=dev pillarenv=aws
    '''
    return _orchestrate(mods=mods,
                        saltenv=saltenv,
                        test=test,
                        exclude=exclude,
                        pillar=pillar,
                        pillarenv=pillarenv)


def running(concurrent=False):
    '''
    Return a list of strings that contain state return data if a state function
    is already running. This function is used to prevent multiple state calls
    from being run at the same time.

    CLI Example:

    .. code-block:: bash

        salt '*' state.running
    '''
    ret = []
    if concurrent:
        return ret
    active = __salt__['saltutil.is_running']('state.*')
    for data in active:
        err = (
            'The function "{0}" is running as PID {1} and was started at '
            '{2} with jid {3}'
        ).format(
            data['fun'],
            data['pid'],
            salt.utils.jid.jid_to_time(data['jid']),
            data['jid'],
        )
        ret.append(err)
    return ret


def _prior_running_states(jid):
    '''
    Return a list of dicts of prior calls to state functions.  This function is
    used to queue state calls so only one is run at a time.
    '''

    ret = []
    active = __salt__['saltutil.is_running']('state.*')
    for data in active:
        try:
            data_jid = int(data['jid'])
        except ValueError:
            continue
        if data_jid < int(jid):
            ret.append(data)
    return ret


def _check_queue(queue, kwargs):
    '''
    Utility function to queue the state run if requested
    and to check for conflicts in currently running states
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running(concurrent=kwargs.get('concurrent', False))
        if conflict:
            __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
            return conflict


def _get_initial_pillar(opts):
    return __pillar__ if __opts__.get('__cli', None) == 'salt-call' \
        and opts['pillarenv'] == __opts__['pillarenv'] \
        else None


def low(data, queue=False, **kwargs):
    '''
    Execute a single low data call

    This function is mostly intended for testing the state system and is not
    likely to be needed in everyday usage.

    CLI Example:

    .. code-block:: bash

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    try:
        st_ = salt.state.State(__opts__, proxy=__proxy__)
    except NameError:
        st_ = salt.state.State(__opts__)
    err = st_.verify_data(data)
    if err:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return err
    ret = st_.call(data)
    if isinstance(ret, list):
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
    if __utils__['state.check_result'](ret):
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_FAILURE
    return ret


def _get_test_value(test=None, **kwargs):
    '''
    Determine the correct value for the test flag.
    '''
    ret = True
    if test is None:
        if salt.utils.args.test_mode(test=test, **kwargs):
            ret = True
        elif __salt__['config.get']('test', omit_opts=True) is True:
            ret = True
        else:
            ret = __opts__.get('test', None)
    else:
        ret = test
    return ret


def high(data, test=None, queue=False, **kwargs):
    '''
    Execute the compound calls stored in a single set of high data

    This function is mostly intended for testing the state system and is not
    likely to be needed in everyday usage.

    CLI Example:

    .. code-block:: bash

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)

    opts['test'] = _get_test_value(test, **kwargs)

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )
    try:
        st_ = salt.state.State(opts,
                               pillar_override,
                               pillar_enc=pillar_enc,
                               proxy=__proxy__,
                               context=__context__,
                               initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.State(opts,
                               pillar_override,
                               pillar_enc=pillar_enc,
                               initial_pillar=_get_initial_pillar(opts))

    ret = st_.call_high(data)
    _set_retcode(ret, highstate=data)
    return ret


def template(tem, queue=False, **kwargs):
    '''
    Execute the information stored in a template file on the minion.

    This function does not ask a master for a SLS file to render but
    instead directly processes the file at the provided path on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' state.template '<Path to template on the minion>'
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    try:
        st_ = salt.state.HighState(opts,
                                   context=__context__,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   context=__context__,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    if not tem.endswith('.sls'):
        tem = '{sls}.sls'.format(sls=tem)
    high_state, errors = st_.render_state(tem,
                                          kwargs.get('saltenv', ''),
                                          '',
                                          None,
                                          local=True)
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return errors
    ret = st_.state.call_high(high_state)
    _set_retcode(ret, highstate=high_state)
    return ret


def template_str(tem, queue=False, **kwargs):
    '''
    Execute the information stored in a string from an sls template

    CLI Example:

    .. code-block:: bash

        salt '*' state.template_str '<Template String>'
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)

    try:
        st_ = salt.state.State(opts,
                               proxy=__proxy__,
                               initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.State(opts, initial_pillar=_get_initial_pillar(opts))
    ret = st_.call_template_str(tem)
    _set_retcode(ret)
    return ret


def apply_(mods=None, **kwargs):
    '''
    .. versionadded:: 2015.5.0

    This function will call :mod:`state.highstate
    <salt.modules.state.highstate>` or :mod:`state.sls
    <salt.modules.state.sls>` based on the arguments passed to this function.
    It exists as a more intuitive way of applying states.

    .. rubric:: APPLYING ALL STATES CONFIGURED IN TOP.SLS (A.K.A. :ref:`HIGHSTATE <running-highstate>`)

    To apply all configured states, simply run ``state.apply``:

    .. code-block:: bash

        salt '*' state.apply

    The following additional arguments are also accepted when applying all
    states configured in top.sls:

    test
        Run states in test-only (dry-run) mode

    mock
        The mock option allows for the state run to execute without actually
        calling any states. This then returns a mocked return which will show
        the requisite ordering as well as fully validate the state run.

        .. versionadded:: 2015.8.4

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.apply stuff pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

    exclude
        Exclude specific states from execution. Accepts a list of sls names, a
        comma-separated string of sls names, or a list of dictionaries
        containing ``sls`` or ``id`` keys. Glob-patterns may be used to match
        multiple states.

        .. code-block:: bash

            salt '*' state.apply exclude=bar,baz
            salt '*' state.apply exclude=foo*
            salt '*' state.apply exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"

    queue : False
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly.

    localconfig
        Optionally, instead of using the minion config, load minion opts from
        the file specified by this argument, and then merge them with the
        options from the minion config. This functionality allows for specific
        states to be run with their own custom minion configuration, including
        different pillars, file_roots, etc.

        .. code-block:: bash

            salt '*' state.apply localconfig=/path/to/minion.yml


    .. rubric:: APPLYING INDIVIDUAL SLS FILES (A.K.A. :py:func:`STATE.SLS <salt.modules.state.sls>`)

    To apply individual SLS files, pass them as a comma-separated list:

    .. code-block:: bash

        # Run the states configured in salt://stuff.sls (or salt://stuff/init.sls)
        salt '*' state.apply stuff

        # Run the states configured in salt://stuff.sls (or salt://stuff/init.sls)
        # and salt://pkgs.sls (or salt://pkgs/init.sls).
        salt '*' state.apply stuff,pkgs

        # Run the states configured in a more deeply nested directory such as salt://my/organized/stuff.sls (or salt://my/organized/stuff/init.sls)
        salt '*' state.apply my.organized.stuff

    The following additional arguments are also accepted when applying
    individual SLS files:

    test
        Run states in test-only (dry-run) mode

    mock
        The mock option allows for the state run to execute without actually
        calling any states. This then returns a mocked return which will show
        the requisite ordering as well as fully validate the state run.

        .. versionadded:: 2015.8.4

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.apply stuff pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

    queue : False
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly.

    concurrent : False
        Execute state runs concurrently instead of serially

        .. warning::

            This flag is potentially dangerous. It is designed for use when
            multiple state runs can safely be run at the same time. Do *not*
            use this flag for performance optimization.

    saltenv
        Specify a salt fileserver environment to be used when applying states

        .. versionchanged:: 0.17.0
            Argument name changed from ``env`` to ``saltenv``

        .. versionchanged:: 2014.7.0
            If no saltenv is specified, the minion config will be checked for an
            ``environment`` parameter and if found, it will be used. If none is
            found, ``base`` will be used. In prior releases, the minion config
            was not checked and ``base`` would always be assumed when the
            saltenv was not explicitly set.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    localconfig
        Optionally, instead of using the minion config, load minion opts from
        the file specified by this argument, and then merge them with the
        options from the minion config. This functionality allows for specific
        states to be run with their own custom minion configuration, including
        different pillars, file_roots, etc.

        .. code-block:: bash

            salt '*' state.apply stuff localconfig=/path/to/minion.yml

    sync_mods
        If specified, the desired custom module types will be synced prior to
        running the SLS files:

        .. code-block:: bash

            salt '*' state.apply stuff sync_mods=states,modules
            salt '*' state.apply stuff sync_mods=all

        .. note::
            This option is ignored when no SLS files are specified, as a
            :ref:`highstate <running-highstate>` automatically syncs all custom
            module types.

        .. versionadded:: 2017.7.8,2018.3.3,2019.2.0
    '''
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


def request(mods=None,
            **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Request that the local admin execute a state run via
    `salt-call state.run_request`.
    All arguments match those of state.apply.

    CLI Example:

    .. code-block:: bash

        salt '*' state.request
        salt '*' state.request stuff
        salt '*' state.request stuff,pkgs
    '''
    kwargs['test'] = True
    ret = apply_(mods, **kwargs)
    notify_path = os.path.join(__opts__['cachedir'], 'req_state.p')
    serial = salt.payload.Serial(__opts__)
    req = check_request()
    req.update({kwargs.get('name', 'default'): {
            'test_run': ret,
            'mods': mods,
            'kwargs': kwargs
            }
        })
    with salt.utils.files.set_umask(0o077):
        try:
            if salt.utils.platform.is_windows():
                # Make sure cache file isn't read-only
                __salt__['cmd.run']('attrib -R "{0}"'.format(notify_path))
            with salt.utils.files.fopen(notify_path, 'w+b') as fp_:
                serial.dump(req, fp_)
        except (IOError, OSError):
            log.error(
                'Unable to write state request file %s. Check permission.',
                notify_path
            )
    return ret


def check_request(name=None):
    '''
    .. versionadded:: 2015.5.0

    Return the state request information, if any

    CLI Example:

    .. code-block:: bash

        salt '*' state.check_request
    '''
    notify_path = os.path.join(__opts__['cachedir'], 'req_state.p')
    serial = salt.payload.Serial(__opts__)
    if os.path.isfile(notify_path):
        with salt.utils.files.fopen(notify_path, 'rb') as fp_:
            req = serial.load(fp_)
        if name:
            return req[name]
        return req
    return {}


def clear_request(name=None):
    '''
    .. versionadded:: 2015.5.0

    Clear out the state execution request without executing it

    CLI Example:

    .. code-block:: bash

        salt '*' state.clear_request
    '''
    notify_path = os.path.join(__opts__['cachedir'], 'req_state.p')
    serial = salt.payload.Serial(__opts__)
    if not os.path.isfile(notify_path):
        return True
    if not name:
        try:
            os.remove(notify_path)
        except (IOError, OSError):
            pass
    else:
        req = check_request()
        if name in req:
            req.pop(name)
        else:
            return False
        with salt.utils.files.set_umask(0o077):
            try:
                if salt.utils.platform.is_windows():
                    # Make sure cache file isn't read-only
                    __salt__['cmd.run']('attrib -R "{0}"'.format(notify_path))
                with salt.utils.files.fopen(notify_path, 'w+b') as fp_:
                    serial.dump(req, fp_)
            except (IOError, OSError):
                log.error(
                    'Unable to write state request file %s. Check permission.',
                    notify_path
                )
    return True


def run_request(name='default', **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Execute the pending state request

    CLI Example:

    .. code-block:: bash

        salt '*' state.run_request
    '''
    req = check_request()
    if name not in req:
        return {}
    n_req = req[name]
    if 'mods' not in n_req or 'kwargs' not in n_req:
        return {}
    req[name]['kwargs'].update(kwargs)
    if 'test' in n_req['kwargs']:
        n_req['kwargs'].pop('test')
    if req:
        ret = apply_(n_req['mods'], **n_req['kwargs'])
        try:
            os.remove(os.path.join(__opts__['cachedir'], 'req_state.p'))
        except (IOError, OSError):
            pass
        return ret
    return {}


def highstate(test=None, queue=False, **kwargs):
    '''
    Retrieve the state data from the salt master for this minion and execute it

    test
        Run states in test-only (dry-run) mode

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.highstate stuff pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

        .. versionchanged:: 2016.3.0
            GPG-encrypted CLI Pillar data is now supported via the GPG
            renderer. See :ref:`here <encrypted-cli-pillar-data>` for details.

    pillar_enc
        Specify which renderer to use to decrypt encrypted data located within
        the ``pillar`` value. Currently, only ``gpg`` is supported.

        .. versionadded:: 2016.3.0

    exclude
        Exclude specific states from execution. Accepts a list of sls names, a
        comma-separated string of sls names, or a list of dictionaries
        containing ``sls`` or ``id`` keys. Glob-patterns may be used to match
        multiple states.

        .. code-block:: bash

            salt '*' state.highstate exclude=bar,baz
            salt '*' state.highstate exclude=foo*
            salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"

    saltenv
        Specify a salt fileserver environment to be used when applying states

        .. versionchanged:: 0.17.0
            Argument name changed from ``env`` to ``saltenv``.

        .. versionchanged:: 2014.7.0
            If no saltenv is specified, the minion config will be checked for a
            ``saltenv`` parameter and if found, it will be used. If none is
            found, ``base`` will be used. In prior releases, the minion config
            was not checked and ``base`` would always be assumed when the
            saltenv was not explicitly set.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    queue : False
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly.

    localconfig
        Optionally, instead of using the minion config, load minion opts from
        the file specified by this argument, and then merge them with the
        options from the minion config. This functionality allows for specific
        states to be run with their own custom minion configuration, including
        different pillars, file_roots, etc.

    mock
        The mock option allows for the state run to execute without actually
        calling any states. This then returns a mocked return which will show
        the requisite ordering as well as fully validate the state run.

        .. versionadded:: 2015.8.4

    CLI Examples:

    .. code-block:: bash

        salt '*' state.highstate

        salt '*' state.highstate whitelist=sls1_to_run,sls2_to_run
        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"

        salt '*' state.highstate pillar="{foo: 'Foo!', bar: 'Bar!'}"
    '''
    if _disabled(['highstate']):
        log.debug('Salt highstate run is disabled. To re-enable, run state.enable highstate')
        ret = {
            'name': 'Salt highstate run is disabled. To re-enable, run state.enable highstate',
            'result': 'False',
            'comment': 'Disabled'
        }
        return ret

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    opts['test'] = _get_test_value(test, **kwargs)

    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    if 'saltenv' in kwargs:
        opts['saltenv'] = kwargs['saltenv']

    if 'pillarenv' in kwargs:
        opts['pillarenv'] = kwargs['pillarenv']

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   context=__context__,
                                   mocked=kwargs.get('mock', False),
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   mocked=kwargs.get('mock', False),
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        return ['Pillar failed to render with the following messages:'] + errors

    st_.push_active()
    orchestration_jid = kwargs.get('orchestration_jid')
    snapper_pre = _snapper_pre(opts, kwargs.get('__pub_jid', 'called localy'))
    try:
        ret = st_.call_highstate(
                exclude=kwargs.get('exclude', []),
                cache=kwargs.get('cache', None),
                cache_name=kwargs.get('cache_name', 'highstate'),
                force=kwargs.get('force', False),
                whitelist=kwargs.get('whitelist'),
                orchestration_jid=orchestration_jid)
    finally:
        st_.pop_active()

    if isinstance(ret, dict) and (__salt__['config.option']('state_data', '') == 'terse' or
            kwargs.get('terse')):
        ret = _filter_running(ret)

    _set_retcode(ret, highstate=st_.building_highstate)
    _snapper_post(opts, kwargs.get('__pub_jid', 'called localy'), snapper_pre)

    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test

    return ret


def sls(mods, test=None, exclude=None, queue=False, sync_mods=None, **kwargs):
    '''
    Execute the states in one or more SLS files

    test
        Run states in test-only (dry-run) mode

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.sls stuff pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override existing Pillar values set via
            ``pillar_roots`` or an external Pillar source.  Pillar values that
            are not included in the kwarg will not be overwritten.

        .. versionchanged:: 2016.3.0
            GPG-encrypted CLI Pillar data is now supported via the GPG
            renderer. See :ref:`here <encrypted-cli-pillar-data>` for details.

    pillar_enc
        Specify which renderer to use to decrypt encrypted data located within
        the ``pillar`` value. Currently, only ``gpg`` is supported.

        .. versionadded:: 2016.3.0

    exclude
        Exclude specific states from execution. Accepts a list of sls names, a
        comma-separated string of sls names, or a list of dictionaries
        containing ``sls`` or ``id`` keys. Glob-patterns may be used to match
        multiple states.

        .. code-block:: bash

            salt '*' state.sls foo,bar,baz exclude=bar,baz
            salt '*' state.sls foo,bar,baz exclude=ba*
            salt '*' state.sls foo,bar,baz exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"

    queue : False
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly.

    concurrent : False
        Execute state runs concurrently instead of serially

        .. warning::

            This flag is potentially dangerous. It is designed for use when
            multiple state runs can safely be run at the same time. Do *not*
            use this flag for performance optimization.

    saltenv
        Specify a salt fileserver environment to be used when applying states

        .. versionchanged:: 0.17.0
            Argument name changed from ``env`` to ``saltenv``.

        .. versionchanged:: 2014.7.0
            If no saltenv is specified, the minion config will be checked for an
            ``environment`` parameter and if found, it will be used. If none is
            found, ``base`` will be used. In prior releases, the minion config
            was not checked and ``base`` would always be assumed when the
            saltenv was not explicitly set.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    localconfig
        Optionally, instead of using the minion config, load minion opts from
        the file specified by this argument, and then merge them with the
        options from the minion config. This functionality allows for specific
        states to be run with their own custom minion configuration, including
        different pillars, file_roots, etc.

    mock
        The mock option allows for the state run to execute without actually
        calling any states. This then returns a mocked return which will show
        the requisite ordering as well as fully validate the state run.

        .. versionadded:: 2015.8.4

    sync_mods
        If specified, the desired custom module types will be synced prior to
        running the SLS files:

        .. code-block:: bash

            salt '*' state.sls stuff sync_mods=states,modules
            salt '*' state.sls stuff sync_mods=all

        .. versionadded:: 2017.7.8,2018.3.3,2019.2.0

    CLI Example:

    .. code-block:: bash

        # Run the states configured in salt://example.sls (or salt://example/init.sls)
        salt '*' state.apply example

        # Run the states configured in salt://core.sls (or salt://core/init.sls)
        # and salt://edit/vim.sls (or salt://edit/vim/init.sls)
        salt '*' state.sls core,edit.vim

        # Run the states configured in a more deeply nested directory such as salt://my/nested/state.sls (or salt://my/nested/state/init.sls)
        salt '*' state.sls my.nested.state

        salt '*' state.sls core exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
        salt '*' state.sls myslsfile pillar="{foo: 'Foo!', bar: 'Bar!'}"
    '''
    concurrent = kwargs.get('concurrent', False)
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    # Modification to __opts__ lost after this if-else
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running(concurrent)
        if conflict:
            __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
            return conflict

    if isinstance(mods, list):
        disabled = _disabled(mods)
    else:
        disabled = _disabled([mods])

    if disabled:
        for state in disabled:
            log.debug(
                'Salt state %s is disabled. To re-enable, run '
                'state.enable %s', state, state
            )
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return disabled

    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)

    opts['test'] = _get_test_value(test, **kwargs)

    # Since this is running a specific SLS file (or files), fall back to the
    # 'base' saltenv if none is configured and none was passed.
    if opts['saltenv'] is None:
        opts['saltenv'] = 'base'

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    serial = salt.payload.Serial(__opts__)
    cfn = os.path.join(
            __opts__['cachedir'],
            '{0}.cache.p'.format(kwargs.get('cache_name', 'highstate'))
            )

    if sync_mods is True:
        sync_mods = ['all']
    if sync_mods is not None:
        sync_mods = salt.utils.args.split_input(sync_mods)
    else:
        sync_mods = []

    if 'all' in sync_mods and sync_mods != ['all']:
        # Prevent unnecessary extra syncing
        sync_mods = ['all']

    for module_type in sync_mods:
        try:
            __salt__['saltutil.sync_{0}'.format(module_type)](
                saltenv=opts['saltenv']
            )
        except KeyError:
            log.warning(
                'Invalid custom module type \'%s\', ignoring',
                module_type
            )

    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   context=__context__,
                                   mocked=kwargs.get('mock', False),
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   mocked=kwargs.get('mock', False),
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        return ['Pillar failed to render with the following messages:'] + errors

    orchestration_jid = kwargs.get('orchestration_jid')
    with salt.utils.files.set_umask(0o077):
        if kwargs.get('cache'):
            if os.path.isfile(cfn):
                with salt.utils.files.fopen(cfn, 'rb') as fp_:
                    high_ = serial.load(fp_)
                    return st_.state.call_high(high_, orchestration_jid)

    # If the state file is an integer, convert to a string then to unicode
    if isinstance(mods, six.integer_types):
        mods = salt.utils.stringutils.to_unicode(str(mods))  # future lint: disable=blacklisted-function

    mods = salt.utils.args.split_input(mods)

    st_.push_active()
    try:
        high_, errors = st_.render_highstate({opts['saltenv']: mods})

        if errors:
            __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
            return errors

        if exclude:
            exclude = salt.utils.args.split_input(exclude)
            if '__exclude__' in high_:
                high_['__exclude__'].extend(exclude)
            else:
                high_['__exclude__'] = exclude
        snapper_pre = _snapper_pre(opts, kwargs.get('__pub_jid', 'called localy'))
        ret = st_.state.call_high(high_, orchestration_jid)
    finally:
        st_.pop_active()
    if __salt__['config.option']('state_data', '') == 'terse' or kwargs.get('terse'):
        ret = _filter_running(ret)
    cache_file = os.path.join(__opts__['cachedir'], 'sls.p')
    with salt.utils.files.set_umask(0o077):
        try:
            if salt.utils.platform.is_windows():
                # Make sure cache file isn't read-only
                __salt__['cmd.run'](['attrib', '-R', cache_file], python_shell=False)
            with salt.utils.files.fopen(cache_file, 'w+b') as fp_:
                serial.dump(ret, fp_)
        except (IOError, OSError):
            log.error(
                'Unable to write to SLS cache file %s. Check permission.',
                cache_file
            )
        _set_retcode(ret, high_)
        # Work around Windows multiprocessing bug, set __opts__['test'] back to
        # value from before this function was run.
        __opts__['test'] = orig_test

        try:
            with salt.utils.files.fopen(cfn, 'w+b') as fp_:
                try:
                    serial.dump(high_, fp_)
                except TypeError:
                    # Can't serialize pydsl
                    pass
        except (IOError, OSError):
            log.error(
                'Unable to write to highstate cache file %s. Do you have permissions?',
                cfn
            )

    _snapper_post(opts, kwargs.get('__pub_jid', 'called localy'), snapper_pre)
    return ret


def top(topfn, test=None, queue=False, **kwargs):
    '''
    Execute a specific top file instead of the default. This is useful to apply
    configurations from a different environment (for example, dev or prod), without
    modifying the default top file.

    queue : False
        Instead of failing immediately when another state run is in progress,
        queue the new state run to begin running once the other has finished.

        This option starts a new thread for each queued state run, so use this
        option sparingly.

    saltenv
        Specify a salt fileserver environment to be used when applying states

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

        .. versionadded:: 2017.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' state.top reverse_top.sls
        salt '*' state.top prod_top.sls exclude=sls_to_exclude
        salt '*' state.top dev_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    opts['test'] = _get_test_value(test, **kwargs)

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )
    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   context=__context__,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   context=__context__,
                                   initial_pillar=_get_initial_pillar(opts))
    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        return ['Pillar failed to render with the following messages:'] + errors

    st_.push_active()
    st_.opts['state_top'] = salt.utils.url.create(topfn)
    ret = {}
    orchestration_jid = kwargs.get('orchestration_jid')
    if 'saltenv' in kwargs:
        st_.opts['state_top_saltenv'] = kwargs['saltenv']
    try:
        snapper_pre = _snapper_pre(opts, kwargs.get('__pub_jid', 'called localy'))
        ret = st_.call_highstate(
                exclude=kwargs.get('exclude', []),
                cache=kwargs.get('cache', None),
                cache_name=kwargs.get('cache_name', 'highstate'),
                orchestration_jid=orchestration_jid)
    finally:
        st_.pop_active()

    _set_retcode(ret, highstate=st_.building_highstate)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    _snapper_post(opts, kwargs.get('__pub_jid', 'called localy'), snapper_pre)
    __opts__['test'] = orig_test
    return ret


def show_highstate(queue=False, **kwargs):
    '''
    Retrieve the highstate data from the salt master and display it

    Custom Pillar data can be passed with the ``pillar`` kwarg.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_highstate
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    st_.push_active()
    try:
        ret = st_.compile_highstate()
    finally:
        st_.pop_active()
    _set_retcode(ret)
    return ret


def show_lowstate(queue=False, **kwargs):
    '''
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        assert False
        return conflict

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    try:
        st_ = salt.state.HighState(opts,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    st_.push_active()
    try:
        ret = st_.compile_low_chunks()
    finally:
        st_.pop_active()
    return ret


def show_state_usage(queue=False, **kwargs):
    '''
    Retrieve the highstate data from the salt master to analyse used and unused states

    Custom Pillar data can be passed with the ``pillar`` kwarg.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_state_usage
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    st_ = salt.state.HighState(__opts__, pillar, pillar_enc=pillar_enc)
    st_.push_active()

    try:
        ret = st_.compile_state_usage()
    finally:
        st_.pop_active()
    _set_retcode(ret)
    return ret


def show_states(queue=False, **kwargs):
    '''
    Returns the list of states that will be applied on highstate.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_states

    .. versionadded:: 2019.2.0

    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        assert False
        return conflict

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    try:
        st_ = salt.state.HighState(opts,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    st_.push_active()
    states = OrderedDict()
    try:
        result = st_.compile_low_chunks()

        if not isinstance(result, list):
            raise Exception(result)

        for s in result:
            if not isinstance(s, dict):
                _set_retcode(result)
                return result
            states[s['__sls__']] = True
    finally:
        st_.pop_active()

    return list(states.keys())


def sls_id(id_, mods, test=None, queue=False, **kwargs):
    '''
    Call a single ID from the named module(s) and handle all requisites

    The state ID comes *before* the module ID(s) on the command line.

    id
        ID to call

    mods
        Comma-delimited list of modules to search for given id and its requisites

    .. versionadded:: 2014.7.0

    saltenv : base
        Specify a salt fileserver environment to be used when applying states

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.sls_id my_state my_module pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override existing Pillar values set via
            ``pillar_roots`` or an external Pillar source.  Pillar values that
            are not included in the kwarg will not be overwritten.

        .. versionadded:: 2018.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' state.sls_id my_state my_module

        salt '*' state.sls_id my_state my_module,a_common_module
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    opts['test'] = _get_test_value(test, **kwargs)

    # Since this is running a specific ID within a specific SLS file, fall back
    # to the 'base' saltenv if none is configured and none was passed.
    if opts['saltenv'] is None:
        opts['saltenv'] = 'base'

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        return ['Pillar failed to render with the following messages:'] + errors

    split_mods = salt.utils.args.split_input(mods)
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({opts['saltenv']: split_mods})
    finally:
        st_.pop_active()
    errors += st_.state.verify_high(high_)
    # Apply requisites to high data
    high_, req_in_errors = st_.state.requisite_in(high_)
    if req_in_errors:
        # This if statement should not be necessary if there were no errors,
        # but it is required to get the unit tests to pass.
        errors.extend(req_in_errors)
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return errors
    chunks = st_.state.compile_high_data(high_)
    ret = {}
    for chunk in chunks:
        if chunk.get('__id__', '') == id_:
            ret.update(st_.state.call_chunk(chunk, {}, chunks))

    _set_retcode(ret, highstate=highstate)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    if not ret:
        raise SaltInvocationError(
            'No matches for ID \'{0}\' found in SLS \'{1}\' within saltenv '
            '\'{2}\''.format(id_, mods, opts['saltenv'])
        )
    return ret


def show_low_sls(mods, test=None, queue=False, **kwargs):
    '''
    Display the low data from a specific sls. The default environment is
    ``base``, use ``saltenv`` to specify a different environment.

    saltenv
        Specify a salt fileserver environment to be used when applying states

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.show_low_sls stuff pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_low_sls foo
        salt '*' state.show_low_sls foo saltenv=dev
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    opts['test'] = _get_test_value(test, **kwargs)

    # Since this is dealing with a specific SLS file (or files), fall back to
    # the 'base' saltenv if none is configured and none was passed.
    if opts['saltenv'] is None:
        opts['saltenv'] = 'base'

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    mods = salt.utils.args.split_input(mods)
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({opts['saltenv']: mods})
    finally:
        st_.pop_active()
    errors += st_.state.verify_high(high_)
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return errors
    ret = st_.state.compile_high_data(high_)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    return ret


def show_sls(mods, test=None, queue=False, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master. The default environment is ``base``, use ``saltenv`` to specify a
    different environment.

    This function does not support topfiles.  For ``top.sls`` please use
    ``show_top`` instead.

    Custom Pillar data can be passed with the ``pillar`` kwarg.

    saltenv
        Specify a salt fileserver environment to be used when applying states

    pillarenv
        Specify a Pillar environment to be used when applying states. This
        can also be set in the minion config file using the
        :conf_minion:`pillarenv` option. When neither the
        :conf_minion:`pillarenv` minion config option nor this CLI argument is
        used, all Pillar environments will be merged together.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim saltenv=dev
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)

    opts['test'] = _get_test_value(test, **kwargs)

    # Since this is dealing with a specific SLS file (or files), fall back to
    # the 'base' saltenv if none is configured and none was passed.
    if opts['saltenv'] is None:
        opts['saltenv'] = 'base'

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    try:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar_override,
                                   pillar_enc=pillar_enc,
                                   initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    mods = salt.utils.args.split_input(mods)
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({opts['saltenv']: mods})
    finally:
        st_.pop_active()
    errors += st_.state.verify_high(high_)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return errors
    return high_


def sls_exists(mods, test=None, queue=False, **kwargs):
    '''
    Tests for the existance the of a specific SLS or list of SLS files on the
    master. Similar to :py:func:`state.show_sls <salt.modules.state.show_sls>`,
    rather than returning state details, returns True or False. The default
    environment is ``base``, use ``saltenv`` to specify a different environment.

    .. versionadded:: 2019.2.0

    saltenv
        Specify a salt fileserver environment from which to look for the SLS files
        specified in the ``mods`` argument

    CLI Example:

    .. code-block:: bash

        salt '*' state.sls_exists core,edit.vim saltenv=dev
    '''
    return isinstance(
        show_sls(mods, test=test, queue=queue, **kwargs),
        dict
    )


def id_exists(ids, mods, test=None, queue=False, **kwargs):
    '''
    Tests for the existence of a specific ID or list of IDs within the
    specified SLS file(s). Similar to :py:func:`state.sls_exists
    <salt.modules.state.sls_exists>`, returns True or False. The default
    environment is base``, use ``saltenv`` to specify a different environment.

    .. versionadded:: 2019.2.0

    saltenv
        Specify a salt fileserver environment from which to look for the SLS files
        specified in the ``mods`` argument

    CLI Example:

    .. code-block:: bash

        salt '*' state.id_exists create_myfile,update_template filestate saltenv=dev
    '''
    ids = salt.utils.args.split_input(ids)
    ids = set(ids)
    sls_ids = set(x['__id__'] for x in show_low_sls(mods, test=test, queue=queue, **kwargs))
    return ids.issubset(sls_ids)


def show_top(queue=False, **kwargs):
    '''
    Return the top data that the minion will use for a highstate

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_top
    '''
    if 'env' in kwargs:
        # "env" is not supported; Use "saltenv".
        kwargs.pop('env')

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict

    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    try:
        st_ = salt.state.HighState(opts,
                                   proxy=__proxy__,
                                   initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.HighState(opts, initial_pillar=_get_initial_pillar(opts))

    errors = _get_pillar_errors(kwargs, pillar=st_.opts['pillar'])
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_PILLAR_FAILURE
        raise CommandExecutionError('Pillar failed to render', info=errors)

    errors = []
    top_ = st_.get_top()
    errors += st_.verify_tops(top_)
    if errors:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return errors
    matches = st_.top_matches(top_)
    return matches


def single(fun, name, test=None, queue=False, **kwargs):
    '''
    Execute a single state function with the named kwargs, returns False if
    insufficient data is sent to the command

    By default, the values of the kwargs will be parsed as YAML. So, you can
    specify lists values, or lists of single entry key-value maps, as you
    would in a YAML salt file. Alternatively, JSON format of keyword values
    is also supported.

    CLI Example:

    .. code-block:: bash

        salt '*' state.single pkg.installed name=vim

    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    comps = fun.split('.')
    if len(comps) < 2:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return 'Invalid function passed'
    kwargs.update({'state': comps[0],
                   'fun': comps[1],
                   '__id__': name,
                   'name': name})
    orig_test = __opts__.get('test', None)
    opts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    opts['test'] = _get_test_value(test, **kwargs)

    pillar_override = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar_override is not None \
            and not isinstance(pillar_override, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    try:
        st_ = salt.state.State(opts,
                               pillar_override,
                               pillar_enc=pillar_enc,
                               proxy=__proxy__,
                               initial_pillar=_get_initial_pillar(opts))
    except NameError:
        st_ = salt.state.State(opts,
                               pillar_override,
                               pillar_enc=pillar_enc,
                               initial_pillar=_get_initial_pillar(opts))
    err = st_.verify_data(kwargs)
    if err:
        __context__['retcode'] = salt.defaults.exitcodes.EX_STATE_COMPILER_ERROR
        return err

    st_._mod_init(kwargs)
    snapper_pre = _snapper_pre(opts, kwargs.get('__pub_jid', 'called localy'))
    ret = {'{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(kwargs):
            st_.call(kwargs)}
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    _snapper_post(opts, kwargs.get('__pub_jid', 'called localy'), snapper_pre)
    __opts__['test'] = orig_test
    return ret


def clear_cache():
    '''
    Clear out cached state files, forcing even cache runs to refresh the cache
    on the next state execution.

    Remember that the state cache is completely disabled by default, this
    execution only applies if cache=True is used in states

    CLI Example:

    .. code-block:: bash

        salt '*' state.clear_cache
    '''
    ret = []
    for fn_ in os.listdir(__opts__['cachedir']):
        if fn_.endswith('.cache.p'):
            path = os.path.join(__opts__['cachedir'], fn_)
            if not os.path.isfile(path):
                continue
            os.remove(path)
            ret.append(fn_)
    return ret


def pkg(pkg_path,
        pkg_sum,
        hash_type,
        test=None,
        **kwargs):
    '''
    Execute a packaged state run, the packaged state run will exist in a
    tarball available locally. This packaged state
    can be generated using salt-ssh.

    CLI Example:

    .. code-block:: bash

        salt '*' state.pkg /tmp/salt_state.tgz 760a9353810e36f6d81416366fc426dc md5
    '''
    # TODO - Add ability to download from salt master or other source
    popts = salt.utils.state.get_sls_opts(__opts__, **kwargs)
    if not os.path.isfile(pkg_path):
        return {}
    if not salt.utils.hashutils.get_hash(pkg_path, hash_type) == pkg_sum:
        return {}
    root = tempfile.mkdtemp()
    s_pkg = tarfile.open(pkg_path, 'r:gz')
    # Verify that the tarball does not extract outside of the intended root
    members = s_pkg.getmembers()
    for member in members:
        if salt.utils.stringutils.to_unicode(member.path).startswith((os.sep, '..{0}'.format(os.sep))):
            return {}
        elif '..{0}'.format(os.sep) in salt.utils.stringutils.to_unicode(member.path):
            return {}
    s_pkg.extractall(root)
    s_pkg.close()
    lowstate_json = os.path.join(root, 'lowstate.json')
    with salt.utils.files.fopen(lowstate_json, 'r') as fp_:
        lowstate = salt.utils.json.load(fp_)
    # Check for errors in the lowstate
    for chunk in lowstate:
        if not isinstance(chunk, dict):
            return lowstate
    pillar_json = os.path.join(root, 'pillar.json')
    if os.path.isfile(pillar_json):
        with salt.utils.files.fopen(pillar_json, 'r') as fp_:
            pillar_override = salt.utils.json.load(fp_)
    else:
        pillar_override = None

    roster_grains_json = os.path.join(root, 'roster_grains.json')
    if os.path.isfile(roster_grains_json):
        with salt.utils.files.fopen(roster_grains_json, 'r') as fp_:
            roster_grains = salt.utils.json.load(fp_)

    if os.path.isfile(roster_grains_json):
        popts['grains'] = roster_grains
    popts['fileclient'] = 'local'
    popts['file_roots'] = {}
    popts['test'] = _get_test_value(test, **kwargs)
    envs = os.listdir(root)
    for fn_ in envs:
        full = os.path.join(root, fn_)
        if not os.path.isdir(full):
            continue
        popts['file_roots'][fn_] = [full]
    st_ = salt.state.State(popts, pillar_override=pillar_override)
    snapper_pre = _snapper_pre(popts, kwargs.get('__pub_jid', 'called localy'))
    ret = st_.call_chunks(lowstate)
    ret = st_.call_listen(lowstate, ret)
    try:
        shutil.rmtree(root)
    except (IOError, OSError):
        pass
    _set_retcode(ret)
    _snapper_post(popts, kwargs.get('__pub_jid', 'called localy'), snapper_pre)
    return ret


def disable(states):
    '''
    Disable state runs.

    CLI Example:

    .. code-block:: bash

        salt '*' state.disable highstate

        salt '*' state.disable highstate,test.succeed_without_changes

    .. note::
        To disable a state file from running provide the same name that would
        be passed in a state.sls call.

        salt '*' state.disable bind.config

    '''
    ret = {
        'res': True,
        'msg': ''
    }

    states = salt.utils.args.split_input(states)

    msg = []
    _disabled = __salt__['grains.get']('state_runs_disabled')
    if not isinstance(_disabled, list):
        _disabled = []

    _changed = False
    for _state in states:
        if _state in _disabled:
            msg.append('Info: {0} state already disabled.'.format(_state))
        else:
            msg.append('Info: {0} state disabled.'.format(_state))
            _disabled.append(_state)
            _changed = True

    if _changed:
        __salt__['grains.setval']('state_runs_disabled', _disabled)

    ret['msg'] = '\n'.join(msg)

    # refresh the grains
    __salt__['saltutil.refresh_modules']()

    return ret


def enable(states):
    '''
    Enable state function or sls run

    CLI Example:

    .. code-block:: bash

        salt '*' state.enable highstate

        salt '*' state.enable test.succeed_without_changes

    .. note::
        To enable a state file from running provide the same name that would
        be passed in a state.sls call.

        salt '*' state.disable bind.config

    '''
    ret = {
        'res': True,
        'msg': ''
    }

    states = salt.utils.args.split_input(states)
    log.debug('states %s', states)

    msg = []
    _disabled = __salt__['grains.get']('state_runs_disabled')
    if not isinstance(_disabled, list):
        _disabled = []

    _changed = False
    for _state in states:
        log.debug('_state %s', _state)
        if _state not in _disabled:
            msg.append('Info: {0} state already enabled.'.format(_state))
        else:
            msg.append('Info: {0} state enabled.'.format(_state))
            _disabled.remove(_state)
            _changed = True

    if _changed:
        __salt__['grains.setval']('state_runs_disabled', _disabled)

    ret['msg'] = '\n'.join(msg)

    # refresh the grains
    __salt__['saltutil.refresh_modules']()

    return ret


def list_disabled():
    '''
    List the states which are currently disabled

    CLI Example:

    .. code-block:: bash

        salt '*' state.list_disabled
    '''
    return __salt__['grains.get']('state_runs_disabled')


def _disabled(funs):
    '''
    Return messages for disabled states
    that match state functions in funs.
    '''
    ret = []
    _disabled = __salt__['grains.get']('state_runs_disabled')
    for state in funs:
        for _state in _disabled:
            if '.*' in _state:
                target_state = _state.split('.')[0]
                target_state = target_state + '.' if not target_state.endswith('.') else target_state
                if state.startswith(target_state):
                    err = (
                        'The state file "{0}" is currently disabled by "{1}", '
                        'to re-enable, run state.enable {1}.'
                    ).format(
                        state,
                        _state,
                    )
                    ret.append(err)
                    continue
            else:
                if _state == state:
                    err = (
                        'The state file "{0}" is currently disabled, '
                        'to re-enable, run state.enable {0}.'
                    ).format(
                        _state,
                    )
                    ret.append(err)
                    continue
    return ret


def event(tagmatch='*',
          count=-1,
          quiet=False,
          sock_dir=None,
          pretty=False,
          node='minion'):
    r'''
    Watch Salt's event bus and block until the given tag is matched

    .. versionadded:: 2016.3.0
    .. versionchanged:: 2019.2.0
        ``tagmatch`` can now be either a glob or regular expression.

    This is useful for utilizing Salt's event bus from shell scripts or for
    taking simple actions directly from the CLI.

    Enable debug logging to see ignored events.

    :param tagmatch: the event is written to stdout for each tag that matches
        this glob or regular expression.
    :param count: this number is decremented for each event that matches the
        ``tagmatch`` parameter; pass ``-1`` to listen forever.
    :param quiet: do not print to stdout; just block
    :param sock_dir: path to the Salt master's event socket file.
    :param pretty: Output the JSON all on a single line if ``False`` (useful
        for shell tools); pretty-print the JSON output if ``True``.
    :param node: Watch the minion-side or master-side event bus.

    CLI Example:

    .. code-block:: bash

        salt-call --local state.event pretty=True
    '''
    with salt.utils.event.get_event(
            node,
            sock_dir or __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True) as sevent:

        while True:
            ret = sevent.get_event(full=True, auto_reconnect=True)
            if ret is None:
                continue

            if salt.utils.stringutils.expr_match(ret['tag'], tagmatch):
                if not quiet:
                    salt.utils.stringutils.print_cli(
                        str('{0}\t{1}').format(  # future lint: blacklisted-function
                            salt.utils.stringutils.to_str(ret['tag']),
                            salt.utils.json.dumps(
                                ret['data'],
                                sort_keys=pretty,
                                indent=None if not pretty else 4)
                        )
                    )
                    sys.stdout.flush()

                if count > 0:
                    count -= 1
                    log.debug('Remaining event matches: %s', count)

                if count == 0:
                    break
            else:
                log.debug('Skipping event tag: %s', ret['tag'])
                continue
