# -*- coding: utf-8 -*-
'''
Control the state system on the minion
'''

# Import python libs
import os
import json
import copy
import shutil
import time
import logging
import tarfile
import datetime
import tempfile

# Import salt libs
import salt.utils
import salt.state
import salt.payload
from salt._compat import string_types


__outputter__ = {
    'sls': 'highstate',
    'top': 'highstate',
    'single': 'highstate',
    'highstate': 'highstate',
}

log = logging.getLogger(__name__)


def _filter_running(runnings):
    '''
    Filter out the result: True + no changes data
    '''
    ret = dict((tag, value) for tag, value in runnings.iteritems()
               if not value['result'] or value['changes'])
    return ret


def _set_retcode(ret):
    '''
    Set the return code based on the data back from the state system
    '''
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
        jid = '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())
    states = _prior_running_states(jid)
    while states:
        time.sleep(1)
        states = _prior_running_states(jid)


def running():
    '''
    Return a dict of state return data if a state function is already running.
    This function is used to prevent multiple state calls from being run at
    the same time.

    CLI Example:

    .. code-block:: bash

        salt '*' state.running
    '''
    ret = []
    active = __salt__['saltutil.is_running']('state.*')
    for data in active:
        err = (
            'The function "{0}" is running as PID {1} and was started at '
            '{2} with jid {3}'
        ).format(
            data['fun'],
            data['pid'],
            salt.utils.jid_to_time(data['jid']),
            data['jid'],
        )
        ret.append(err)
    return ret


def _prior_running_states(jid):
    """
    Return a list of dicts of prior calls to state functions.  This function is
    used to queue state calls so only one is run at a time.
    """

    ret = []
    active = __salt__['saltutil.is_running']('state.*')
    for data in active:
        if int(data['jid']) < int(jid):
            ret.append(data)
    return ret


def low(data, queue=False, **kwargs):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
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


def high(data, queue=False, **kwargs):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example:

    .. code-block:: bash

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    st_ = salt.state.State(__opts__)
    ret = st_.call_high(data)
    _set_retcode(ret)
    return ret


def template(tem, queue=False, **kwargs):
    '''
    Execute the information stored in a template file on the minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.template '<Path to template on the minion>'
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    st_ = salt.state.State(__opts__)
    ret = st_.call_template(tem)
    _set_retcode(ret)
    return ret


def template_str(tem, queue=False, **kwargs):
    '''
    Execute the information stored in a string from an sls template

    CLI Example:

    .. code-block:: bash

        salt '*' state.template_str '<Template String>'
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    st_ = salt.state.State(__opts__)
    ret = st_.call_template_str(tem)
    _set_retcode(ret)
    return ret


def highstate(test=None, queue=False, **kwargs):
    '''
    Retrieve the state data from the salt master for this minion and execute it

    CLI Example:

    .. code-block:: bash

        salt '*' state.highstate

        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    orig_test = __opts__.get('test', None)
    opts = copy.deepcopy(__opts__)

    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)

    if 'env' in kwargs:
        opts['environment'] = kwargs['env']

    pillar = kwargs.get('pillar')

    st_ = salt.state.HighState(opts, pillar)
    st_.push_active()
    try:
        ret = st_.call_highstate(
                exclude=kwargs.get('exclude', []),
                cache=kwargs.get('cache', None),
                cache_name=kwargs.get('cache_name', 'highstate'),
                force=kwargs.get('force', False)
                )
    finally:
        st_.pop_active()

    if __salt__['config.option']('state_data', '') == 'terse' or \
            kwargs.get('terse'):
        ret = _filter_running(ret)
    serial = salt.payload.Serial(__opts__)
    cache_file = os.path.join(__opts__['cachedir'], 'highstate.p')

    # Not 100% if this should be fatal or not,
    # but I'm guessing it likely should not be.
    cumask = os.umask(191)
    try:
        with salt.utils.fopen(cache_file, 'w+') as fp_:
            serial.dump(ret, fp_)
    except (IOError, OSError):
        msg = 'Unable to write to "state.highstate" cache file {0}'
        log.error(msg.format(cache_file))
    os.umask(cumask)
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    return ret


def sls(mods, env='base', test=None, exclude=None, queue=False, **kwargs):
    '''
    Execute a set list of state modules from an environment, default
    environment is base

    CLI Example:

    .. code-block:: bash

        salt '*' state.sls core,edit.vim dev
        salt '*' state.sls core exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''

    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    orig_test = __opts__.get('test', None)
    opts = copy.deepcopy(__opts__)

    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    elif test is not None:
        opts['test'] = test
    else:
        opts['test'] = __opts__.get('test', None)

    pillar = kwargs.get('pillar')

    serial = salt.payload.Serial(__opts__)
    cfn = os.path.join(
            __opts__['cachedir'],
            '{0}.cache.p'.format(kwargs.get('cache_name', 'highstate'))
            )

    st_ = salt.state.HighState(opts, pillar)

    if kwargs.get('cache'):
        if os.path.isfile(cfn):
            with salt.utils.fopen(cfn, 'r') as fp_:
                high_ = serial.load(fp_)
                return st_.state.call_high(high_)

    if isinstance(mods, string_types):
        mods = mods.split(',')

    st_.push_active()
    try:
        high_, errors = st_.render_highstate({env: mods})

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
    cumask = os.umask(191)
    try:
        with salt.utils.fopen(cache_file, 'w+') as fp_:
            serial.dump(ret, fp_)
    except (IOError, OSError):
        msg = 'Unable to write to "state.sls" cache file {0}'
        log.error(msg.format(cache_file))
    os.umask(cumask)
    _set_retcode(ret)
    # Work around Windows multiprocessing bug, set __opts__['test'] back to
    # value from before this function was run.
    __opts__['test'] = orig_test
    with salt.utils.fopen(cfn, 'w+') as fp_:
        try:
            serial.dump(high_, fp_)
        except TypeError:
            # Can't serialize pydsl
            pass
    return ret


def top(topfn, test=None, queue=False, **kwargs):
    '''
    Execute a specific top file instead of the default

    CLI Example:

    .. code-block:: bash

        salt '*' state.top reverse_top.sls
        salt '*' state.top reverse_top.sls exclude=sls_to_exclude
        salt '*' state.top reverse_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    orig_test = __opts__.get('test', None)
    opts = copy.deepcopy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.state.HighState(opts)
    st_.push_active()
    st_.opts['state_top'] = os.path.join('salt://', topfn)
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

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_highstate
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    st_ = salt.state.HighState(__opts__)
    st_.push_active()
    try:
        ret = st_.compile_highstate()
    finally:
        st_.pop_active()
    if isinstance(ret, list):
        __context__['retcode'] = 1
    return ret


def show_lowstate(queue=False, **kwargs):
    '''
    List out the low data that will be applied to this minion

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_lowstate
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    st_ = salt.state.HighState(__opts__)
    st_.push_active()
    try:
        ret = st_.compile_low_chunks()
    finally:
        st_.pop_active()
    return ret


def show_low_sls(mods, env='base', test=None, queue=False, **kwargs):
    '''
    Display the low data from a specific sls

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_low_sls foo
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    orig_test = __opts__.get('test', None)
    opts = copy.deepcopy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.state.HighState(opts)
    if isinstance(mods, string_types):
        mods = mods.split(',')
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({env: mods})
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


def show_sls(mods, env='base', test=None, queue=False, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example:

    .. code-block:: bash

        salt '*' state.show_sls core,edit.vim dev
    '''
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    orig_test = __opts__.get('test', None)
    opts = copy.deepcopy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.state.HighState(opts)
    if isinstance(mods, string_types):
        mods = mods.split(',')
    st_.push_active()
    try:
        high_, errors = st_.render_highstate({env: mods})
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
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
            return conflict
    st_ = salt.state.HighState(__opts__)
    errors = []
    top_ = st_.get_top()
    errors += st_.verify_tops(top_)
    if errors:
        __context__['retcode'] = 1
        return errors
    matches = st_.top_matches(top_)
    return matches

# Just commenting out, someday I will get this working
#def show_masterstate():
#    '''
#    Display the data gathered from the master compiled state
#
#    CLI Example:
#
#    .. code-block:: bash
#
#        salt '*' state.show_masterstate
#    '''
#    st_ = salt.state.RemoteHighState(__opts__, __grains__)
#    return st_.compile_master()


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
    if queue:
        _wait(kwargs.get('__pub_jid'))
    else:
        conflict = running()
        if conflict:
            __context__['retcode'] = 1
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
    opts = copy.deepcopy(__opts__)
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = __opts__.get('test', None)
    st_ = salt.state.State(opts)
    err = st_.verify_data(kwargs)
    if err:
        __context__['retcode'] = 1
        return err

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
        # Verify that the tarball does not extract outside of the intended
        # root
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
    popts = copy.deepcopy(__opts__)
    popts['fileclient'] = 'local'
    popts['file_roots'] = {}
    if salt.utils.test_mode(test=test, **kwargs):
        popts['test'] = True
    else:
        popts['test'] = __opts__.get('test', None)
    for fn_ in os.listdir(root):
        full = os.path.join(root, fn_)
        if not os.path.isdir(full):
            continue
        popts['file_roots'][fn_] = [full]
    st_ = salt.state.State(popts)
    ret = st_.call_chunks(lowstate)
    try:
        shutil.rmtree(root)
    except (IOError, OSError):
        pass
    return ret
