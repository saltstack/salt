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
from __future__ import absolute_import, print_function
import copy
import fnmatch
import json
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
import salt.utils
import salt.utils.jid
import salt.utils.url
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
import salt.ext.six as six

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


def _filter_running(runnings):
    '''
    Filter out the result: True + no changes data
    '''
    ret = dict((tag, value) for tag, value in six.iteritems(runnings)
               if not value['result'] or value['changes'])
    return ret


def _set_retcode(ret):
    '''
    Set the return code based on the data back from the state system
    '''

    # Set default retcode to 0
    __context__['retcode'] = 0

    if isinstance(ret, list):
        __context__['retcode'] = 1
        return
    if not salt.utils.check_state_result(ret):
        __context__['retcode'] = 2


def _check_pillar(kwargs):
    '''
    Check the pillar for errors, refuse to run the state if there are errors
    in the pillar and return the pillar errors
    '''
    if kwargs.get('force'):
        return True
    if '_errors' in __pillar__:
        return False
    return True


def _wait(jid):
    '''
    Wait for all previously started state jobs to finish running
    '''
    if jid is None:
        jid = salt.utils.jid.gen_jid()
    states = _prior_running_states(jid)
    while states:
        time.sleep(1)
        states = _prior_running_states(jid)


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
        if int(data['jid']) < int(jid):
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
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict


def _get_opts(localconfig=None):
    '''
    Return a copy of the opts for use, optionally load a local config on top
    '''
    opts = copy.deepcopy(__opts__)
    if localconfig:
        opts = salt.config.minion_config(localconfig, defaults=opts)
    return opts


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
        __context__['retcode'] = 1
        return err
    ret = st_.call(data)
    if isinstance(ret, list):
        __context__['retcode'] = 1
    if salt.utils.check_state_result(ret):
        __context__['retcode'] = 2
    return ret


def high(data, test=False, queue=False, **kwargs):
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
    opts = _get_opts(kwargs.get('localconfig'))

    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    elif test is not None:
        opts['test'] = test
    else:
        opts['test'] = __opts__.get('test', None)

    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )
    try:
        st_ = salt.state.State(__opts__, pillar, pillar_enc=pillar_enc, proxy=__proxy__,
                context=__context__)
    except NameError:
        st_ = salt.state.State(__opts__, pillar, pillar_enc=pillar_enc)

    ret = st_.call_high(data)
    _set_retcode(ret)
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
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    if 'saltenv' in kwargs:
        saltenv = kwargs['saltenv']
    else:
        saltenv = ''

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    st_ = salt.state.HighState(__opts__, context=__context__)
    if not tem.endswith('.sls'):
        tem = '{sls}.sls'.format(sls=tem)
    high_state, errors = st_.render_state(tem, saltenv, '', None, local=True)
    if errors:
        __context__['retcode'] = 1
        return errors
    ret = st_.state.call_high(high_state)
    _set_retcode(ret)
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
    try:
        st_ = salt.state.State(__opts__, proxy=__proxy__)
    except NameError:
        st_ = salt.state.State(__opts__)
    ret = st_.call_template_str(tem)
    _set_retcode(ret)
    return ret


def apply_(mods=None,
          **kwargs):
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

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.apply test pillar='{"foo": "bar"}'

        .. note::
            Values passed this way will override Pillar values set via
            ``pillar_roots`` or an external Pillar source.

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

        # Run the states configured in salt://test.sls (or salt://test/init.sls)
        salt '*' state.apply test
        # Run the states configured in salt://test.sls (or salt://test/init.sls)
        # and salt://pkgs.sls (or salt://pkgs/init.sls).
        salt '*' state.apply test,pkgs

    The following additional arguments are also accepted when applying
    individual SLS files:

    test
        Run states in test-only (dry-run) mode

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.apply test pillar='{"foo": "bar"}'

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

    saltenv : None
        Specify a salt fileserver environment to be used when applying states

        .. versionchanged:: 0.17.0
            Argument name changed from ``env`` to ``saltenv``

        .. versionchanged:: 2014.7.0
            If no saltenv is specified, the minion config will be checked for a
            ``saltenv`` parameter and if found, it will be used. If none is
            found, ``base`` will be used. In prior releases, the minion config
            was not checked and ``base`` would always be assumed when the
            saltenv was not explicitly set.

    pillarenv
        Specify a Pillar environment to be used when applying states. By
        default, all Pillar environments will be merged together and used.

    localconfig
        Optionally, instead of using the minion config, load minion opts from
        the file specified by this argument, and then merge them with the
        options from the minion config. This functionality allows for specific
        states to be run with their own custom minion configuration, including
        different pillars, file_roots, etc.

        .. code-block:: bash

            salt '*' state.apply test localconfig=/path/to/minion.yml
    '''
    if mods:
        return sls(mods, **kwargs)
    return highstate(**kwargs)


def request(mods=None,
            **kwargs):
    '''
    .. versionadded:: 2015.5.0

    Request that the local admin execute a state run via
    `salt-call state.run_request`
    All arguments match state.apply

    CLI Example:

    .. code-block:: bash

        salt '*' state.request
        salt '*' state.request test
        salt '*' state.request test,pkgs
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
    cumask = os.umask(0o77)
    try:
        if salt.utils.is_windows():
            # Make sure cache file isn't read-only
            __salt__['cmd.run']('attrib -R "{0}"'.format(notify_path))
        with salt.utils.fopen(notify_path, 'w+b') as fp_:
            serial.dump(req, fp_)
    except (IOError, OSError):
        msg = 'Unable to write state request file {0}. Check permission.'
        log.error(msg.format(notify_path))
    os.umask(cumask)
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
        with salt.utils.fopen(notify_path, 'rb') as fp_:
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
        cumask = os.umask(0o77)
        try:
            if salt.utils.is_windows():
                # Make sure cache file isn't read-only
                __salt__['cmd.run']('attrib -R "{0}"'.format(notify_path))
            with salt.utils.fopen(notify_path, 'w+b') as fp_:
                serial.dump(req, fp_)
        except (IOError, OSError):
            msg = 'Unable to write state request file {0}. Check permission.'
            log.error(msg.format(notify_path))
        os.umask(cumask)
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


def highstate(test=None,
              queue=False,
              **kwargs):
    '''
    Retrieve the state data from the salt master for this minion and execute it

    test
        Run states in test-only (dry-run) mode

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.apply test pillar='{"foo": "bar"}'

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

    mock:
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

    opts = _get_opts(kwargs.get('localconfig'))

    if test is None:
        if salt.utils.test_mode(test=test, **kwargs):
            opts['test'] = True
        else:
            opts['test'] = __opts__.get('test', None)
    else:
        opts['test'] = test

    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    if 'saltenv' in kwargs:
        opts['environment'] = kwargs['saltenv']

    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    if 'pillarenv' in kwargs:
        opts['pillarenv'] = kwargs['pillarenv']

    try:
        st_ = salt.state.HighState(opts,
                                   pillar,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   context=__context__,
                                   mocked=kwargs.get('mock', False))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   mocked=kwargs.get('mock', False))

    st_.push_active()
    try:
        ret = st_.call_highstate(
                exclude=kwargs.get('exclude', []),
                cache=kwargs.get('cache', None),
                cache_name=kwargs.get('cache_name', 'highstate'),
                force=kwargs.get('force', False),
                whitelist=kwargs.get('whitelist')
                )
    finally:
        st_.pop_active()

    if __salt__['config.option']('state_data', '') == 'terse' or \
            kwargs.get('terse'):
        ret = _filter_running(ret)

    serial = salt.payload.Serial(__opts__)
    cache_file = os.path.join(__opts__['cachedir'], 'highstate.p')
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    return ret


def sls(mods,
        saltenv=None,
        test=None,
        exclude=None,
        queue=False,
        pillarenv=None,
        **kwargs):
    '''
    Execute the states in one or more SLS files

    test
        Run states in test-only (dry-run) mode

    pillar
        Custom Pillar values, passed as a dictionary of key-value pairs

        .. code-block:: bash

            salt '*' state.apply test pillar='{"foo": "bar"}'

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

    saltenv : None
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

        Specify a Pillar environment to be used when applying states. By
        default, all Pillar environments will be merged together and used.

    localconfig

        Optionally, instead of using the minion config, load minion opts from
        the file specified by this argument, and then merge them with the
        options from the minion config. This functionality allows for specific
        states to be run with their own custom minion configuration, including
        different pillars, file_roots, etc.

    mock:
        The mock option allows for the state run to execute without actually
        calling any states. This then returns a mocked return which will show
        the requisite ordering as well as fully validate the state run.

        .. versionadded:: 2015.8.4

    CLI Example:

    .. code-block:: bash

        salt '*' state.sls core,edit.vim dev
        salt '*' state.sls core exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"

        salt '*' state.sls myslsfile pillar="{foo: 'Foo!', bar: 'Bar!'}"
    '''
    concurrent = kwargs.get('concurrent', False)
    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    if saltenv is None:
        if __opts__.get('environment', None):
            saltenv = __opts__['environment']
        else:
            saltenv = 'base'

    if not pillarenv:
        if __opts__.get('pillarenv', None):
            pillarenv = __opts__['pillarenv']

    # Modification to __opts__ lost after this if-else
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running(concurrent)
        if conflict:
            __context__['retcode'] = 1
            return conflict

    # Ensure desired environment
    __opts__['environment'] = saltenv
    __opts__['pillarenv'] = pillarenv

    if isinstance(mods, list):
        disabled = _disabled(mods)
    else:
        disabled = _disabled([mods])

    if disabled:
        for state in disabled:
            log.debug('Salt state {0} run is disabled. To re-enable, run state.enable {0}'.format(state))
        __context__['retcode'] = 1
        return disabled

    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    orig_test = __opts__.get('test', None)
    opts = _get_opts(kwargs.get('localconfig'))

    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    elif test is not None:
        opts['test'] = test
    else:
        opts['test'] = __opts__.get('test', None)

    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    serial = salt.payload.Serial(__opts__)
    cfn = os.path.join(
            __opts__['cachedir'],
            '{0}.cache.p'.format(kwargs.get('cache_name', 'highstate'))
            )

    try:
        st_ = salt.state.HighState(opts,
                                   pillar,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   proxy=__proxy__,
                                   context=__context__,
                                   mocked=kwargs.get('mock', False))
    except NameError:
        st_ = salt.state.HighState(opts,
                                   pillar,
                                   kwargs.get('__pub_jid'),
                                   pillar_enc=pillar_enc,
                                   mocked=kwargs.get('mock', False))

    umask = os.umask(0o77)
    if kwargs.get('cache'):
        if os.path.isfile(cfn):
            with salt.utils.fopen(cfn, 'rb') as fp_:
                high_ = serial.load(fp_)
                return st_.state.call_high(high_)
    os.umask(umask)

    if isinstance(mods, six.string_types):
        mods = mods.split(',')

    st_.push_active()
    try:
        high_, errors = st_.render_highstate({saltenv: mods})

        if errors:
            __context__['retcode'] = 1
            return errors

        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(',')
            if '__exclude__' in high_:
                high_['__exclude__'].extend(exclude)
            else:
                high_['__exclude__'] = exclude
        ret = st_.state.call_high(high_)
    finally:
        st_.pop_active()
    if __salt__['config.option']('state_data', '') == 'terse' or kwargs.get('terse'):
        ret = _filter_running(ret)
    cache_file = os.path.join(__opts__['cachedir'], 'sls.p')
    cumask = os.umask(0o77)
    try:
        if salt.utils.is_windows():
            # Make sure cache file isn't read-only
            __salt__['cmd.run'](['attrib', '-R', cache_file], python_shell=False)
        with salt.utils.fopen(cache_file, 'w+b') as fp_:
            serial.dump(ret, fp_)
    except (IOError, OSError):
        msg = 'Unable to write to SLS cache file {0}. Check permission.'
        log.error(msg.format(cache_file))
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test

    try:
        with salt.utils.fopen(cfn, 'w+b') as fp_:
            try:
                serial.dump(high_, fp_)
            except TypeError:
                # Can't serialize pydsl
                pass
    except (IOError, OSError):
        msg = 'Unable to write to highstate cache file {0}. Do you have permissions?'
        log.error(msg.format(cfn))
    os.umask(cumask)
    return ret


def top(topfn,
        test=None,
        queue=False,
        saltenv=None,
        **kwargs):
    '''
    Execute a specific top file instead of the default. This is useful to apply
    configurations from a different environment (for example, dev or prod), without
    modifying the default top file.

    CLI Example:

    .. code-block:: bash

        salt '*' state.top reverse_top.sls
        salt '*' state.top prod_top.sls exclude=sls_to_exclude
        salt '*' state.top dev_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    orig_test = __opts__.get('test', None)
    opts = _get_opts(kwargs.get('localconfig'))
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)

    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    st_ = salt.state.HighState(opts, pillar, pillar_enc=pillar_enc, context=__context__)
    st_.push_active()
    st_.opts['state_top'] = salt.utils.url.create(topfn)
    if saltenv:
        st_.opts['state_top_saltenv'] = saltenv
    try:
        ret = st_.call_highstate(
                exclude=kwargs.get('exclude', []),
                cache=kwargs.get('cache', None),
                cache_name=kwargs.get('cache_name', 'highstate')
                )
    finally:
        st_.pop_active()
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
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
    st_ = salt.state.HighState(__opts__)
    st_.push_active()
    try:
        ret = st_.compile_low_chunks()
    finally:
        st_.pop_active()
    return ret


def sls_id(
        id_,
        mods,
        saltenv='base',
        test=None,
        queue=False,
        **kwargs):
    '''
    Call a single ID from the named module(s) and handle all requisites

    The state ID comes *before* the module ID(s) on the command line.

    .. versionadded:: 2014.7.0

    CLI Example:

    .. code-block:: bash

        salt '*' state.sls_id my_state my_module
    '''
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = _get_opts(kwargs.get('localconfig'))
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    if 'pillarenv' in kwargs:
        opts['pillarenv'] = kwargs['pillarenv']
    st_ = salt.state.HighState(opts)
    if isinstance(mods, six.string_types):
        split_mods = mods.split(',')
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({saltenv: split_mods})
    finally:
        st_.pop_active()
    errors += st_.state.verify_high(high_)
    if errors:
        __context__['retcode'] = 1
        return errors
    chunks = st_.state.compile_high_data(high_)
    ret = {}
    for chunk in chunks:
        if chunk.get('__id__', '') == id_:
            ret.update(st_.state.call_chunk(chunk, {}, chunks))
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    if not ret:
        raise SaltInvocationError(
            'No matches for ID \'{0}\' found in SLS \'{1}\' within saltenv '
            '\'{2}\''.format(id_, mods, saltenv)
        )
    return ret


def show_low_sls(mods,
                 saltenv='base',
                 test=None,
                 queue=False,
                 **kwargs):
    '''
    Display the low data from a specific sls. The default environment is
    ``base``, use ``saltenv`` to specify a different environment.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_low_sls foo
    '''
    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = _get_opts(kwargs.get('localconfig'))
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    if 'pillarenv' in kwargs:
        opts['pillarenv'] = kwargs['pillarenv']
    st_ = salt.state.HighState(opts)
    if isinstance(mods, six.string_types):
        mods = mods.split(',')
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({saltenv: mods})
    finally:
        st_.pop_active()
    errors += st_.state.verify_high(high_)
    if errors:
        __context__['retcode'] = 1
        return errors
    ret = st_.state.compile_high_data(high_)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    return ret


def show_sls(mods, saltenv='base', test=None, queue=False, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master. The default environment is ``base``, use ``saltenv`` to specify a
    different environment.

    This function does not support topfiles.  For ``top.sls`` please use
    ``show_top`` instead.

    Custom Pillar data can be passed with the ``pillar`` kwarg.

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    orig_test = __opts__.get('test', None)
    opts = _get_opts(kwargs.get('localconfig'))

    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)

    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    if 'pillarenv' in kwargs:
        opts['pillarenv'] = kwargs['pillarenv']

    st_ = salt.state.HighState(opts, pillar, pillar_enc=pillar_enc)
    if isinstance(mods, six.string_types):
        mods = mods.split(',')
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({saltenv: mods})
    finally:
        st_.pop_active()
    errors += st_.state.verify_high(high_)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    if errors:
        __context__['retcode'] = 1
        return errors
    return high_


def show_top(queue=False, **kwargs):
    '''
    Return the top data that the minion will use for a highstate

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_top
    '''
    opts = copy.deepcopy(__opts__)

    if 'env' in kwargs:
        salt.utils.warn_until(
            'Oxygen',
            'Parameter \'env\' has been detected in the argument list.  This '
            'parameter is no longer used and has been replaced by \'saltenv\' '
            'as of Salt Carbon.  This warning will be removed in Salt Oxygen.'
            )
        kwargs.pop('env')

    if 'saltenv' in kwargs:
        opts['environment'] = kwargs['saltenv']
    conflict = _check_queue(queue, kwargs)
    if conflict is not None:
        return conflict
    st_ = salt.state.HighState(opts)
    errors = []
    top_ = st_.get_top()
    errors += st_.verify_tops(top_)
    if errors:
        __context__['retcode'] = 1
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
        __context__['retcode'] = 1
        return 'Invalid function passed'
    kwargs.update({'state': comps[0],
                   'fun': comps[1],
                   '__id__': name,
                   'name': name})
    orig_test = __opts__.get('test', None)
    opts = _get_opts(kwargs.get('localconfig'))
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)

    pillar = kwargs.get('pillar')
    pillar_enc = kwargs.get('pillar_enc')
    if pillar_enc is None \
            and pillar is not None \
            and not isinstance(pillar, dict):
        raise SaltInvocationError(
            'Pillar data must be formatted as a dictionary, unless pillar_enc '
            'is specified.'
        )

    try:
        st_ = salt.state.State(opts, pillar, pillar_enc=pillar_enc, proxy=__proxy__)
    except NameError:
        st_ = salt.state.State(opts, pillar, pillar_enc=pillar_enc)
    err = st_.verify_data(kwargs)
    if err:
        __context__['retcode'] = 1
        return err

    st_._mod_init(kwargs)
    ret = {'{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(kwargs):
            st_.call(kwargs)}
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
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


def pkg(pkg_path, pkg_sum, hash_type, test=False, **kwargs):
    '''
    Execute a packaged state run, the packaged state run will exist in a
    tarball available locally. This packaged state
    can be generated using salt-ssh.

    CLI Example:

    .. code-block:: bash

        salt '*' state.pkg /tmp/state_pkg.tgz
    '''
    # TODO - Add ability to download from salt master or other source
    if not os.path.isfile(pkg_path):
        return {}
    if not salt.utils.get_hash(pkg_path, hash_type) == pkg_sum:
        return {}
    root = tempfile.mkdtemp()
    s_pkg = tarfile.open(pkg_path, 'r:gz')
    # Verify that the tarball does not extract outside of the intended root
    members = s_pkg.getmembers()
    for member in members:
        if member.path.startswith((os.sep, '..{0}'.format(os.sep))):
            return {}
        elif '..{0}'.format(os.sep) in member.path:
            return {}
    s_pkg.extractall(root)
    s_pkg.close()
    lowstate_json = os.path.join(root, 'lowstate.json')
    with salt.utils.fopen(lowstate_json, 'r') as fp_:
        lowstate = json.load(fp_, object_hook=salt.utils.decode_dict)
    # Check for errors in the lowstate
    for chunk in lowstate:
        if not isinstance(chunk, dict):
            return lowstate
    pillar_json = os.path.join(root, 'pillar.json')
    if os.path.isfile(pillar_json):
        with salt.utils.fopen(pillar_json, 'r') as fp_:
            pillar = json.load(fp_)
    else:
        pillar = None
    popts = _get_opts(kwargs.get('localconfig'))
    popts['fileclient'] = 'local'
    popts['file_roots'] = {}
    if salt.utils.test_mode(test=test, **kwargs):
        popts['test'] = True
    else:
        popts['test'] = __opts__.get('test', None)
    envs = os.listdir(root)
    for fn_ in envs:
        full = os.path.join(root, fn_)
        if not os.path.isdir(full):
            continue
        popts['file_roots'][fn_] = [full]
    st_ = salt.state.State(popts, pillar=pillar)
    ret = st_.call_chunks(lowstate)
    try:
        shutil.rmtree(root)
    except (IOError, OSError):
        pass
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

    if isinstance(states, six.string_types):
        states = states.split(',')

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

    if isinstance(states, six.string_types):
        states = states.split(',')
    log.debug("states {0}".format(states))

    msg = []
    _disabled = __salt__['grains.get']('state_runs_disabled')
    if not isinstance(_disabled, list):
        _disabled = []

    _changed = False
    for _state in states:
        log.debug("_state {0}".format(_state))
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

    This is useful for utilizing Salt's event bus from shell scripts or for
    taking simple actions directly from the CLI.

    Enable debug logging to see ignored events.

    :param tagmatch: the event is written to stdout for each tag that matches
        this pattern; uses the same matching semantics as Salt's Reactor.
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
    sevent = salt.utils.event.get_event(
            node,
            sock_dir or __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__,
            listen=True)

    while True:
        ret = sevent.get_event(full=True)
        if ret is None:
            continue

        if fnmatch.fnmatch(ret['tag'], tagmatch):
            if not quiet:
                print('{0}\t{1}'.format(
                    ret['tag'],
                    json.dumps(
                        ret['data'],
                        sort_keys=pretty,
                        indent=None if not pretty else 4)))
                sys.stdout.flush()

            count -= 1
            log.debug('Remaining event matches: %s', count)

            if count == 0:
                break
        else:
            log.debug('Skipping event tag: %s', ret['tag'])
            continue
