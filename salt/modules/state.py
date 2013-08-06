'''
Control the state system on the minion
'''

# Import python libs
import os
import copy
import logging
import json

# Import salt libs
import salt.utils
import salt.state
import salt.payload
from salt.utils.yamlloader import load as _yaml_load
from salt.utils.yamlloader import CustomLoader as _YamlCustomLoader
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
    ret = dict((tag, value) for tag, value in runnings.iteritems() if not value['result'] or value['changes'])
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
    Check the pillar for errors, refuse to run the state it there are errors
    in the pillar and return the pillar errors
    '''
    if kwargs.get('force'):
        return True
    if '_errors' in __pillar__:
        return False
    return True


def running():
    '''
    Return a dict of state return data if a state function is already running.
    This function is used to prevent multiple state calls from being run at
    the same time.

    CLI Example::

        salt '*' state.running
    '''
    ret = []
    active = __salt__['saltutil.is_running']('state.*')
    for data in active:
        err = ('The function "{0}" is running as PID {1} and was started at '
               '{2} with jid {3}').format(
                data['fun'],
                data['pid'],
                salt.utils.jid_to_time(data['jid']),
                data['jid'],
                )
        ret.append(err)
    return ret


def low(data):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example::

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
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


def high(data):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example::

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    st_ = salt.state.State(__opts__)
    ret = st_.call_high(data)
    _set_retcode(ret)
    return ret


def template(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example::

        salt '*' state.template '<Path to template on the minion>'
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    st_ = salt.state.State(__opts__)
    ret = st_.call_template(tem)
    _set_retcode(ret)
    return ret


def template_str(tem):
    '''
    Execute the information stored in a string from an sls template

    CLI Example::

        salt '*' state.template_str '<Template String>'
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    st_ = salt.state.State(__opts__)
    ret = st_.call_template_str(tem)
    _set_retcode(ret)
    return ret


def highstate(test=None, **kwargs):
    '''
    Retrive the state data from the salt master for this minion and execute it

    CLI Example::

        salt '*' state.highstate

        salt '*' state.highstate exclude=sls_to_exclude
        salt '*' state.highstate exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    opts = copy.copy(__opts__)

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
                cache_name=kwargs.get('cache_name', 'highstate')
                )
    finally:
        st_.pop_active()
    if __salt__['config.option']('state_data', '') == 'terse' or kwargs.get('terse'):
        ret = _filter_running(ret)
    serial = salt.payload.Serial(__opts__)
    cache_file = os.path.join(__opts__['cachedir'], 'highstate.p')

    # Not 100% if this should be fatal or not,
    # but I'm guessing it likely should not be.
    try:
        with salt.utils.fopen(cache_file, 'w+') as fp_:
            serial.dump(ret, fp_)
    except (IOError, OSError):
        msg = 'Unable to write to "state.highstate" cache file {0}'
        log.error(msg.format(cache_file))

    _set_retcode(ret)
    return ret


def sls(mods, env='base', test=None, exclude=None, **kwargs):
    '''
    Execute a set list of state modules from an environment, default
    environment is base

    CLI Example::

        salt '*' state.sls core,edit.vim dev

        salt '*' state.sls core exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''

    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    opts = copy.copy(__opts__)

    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
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
            with open(cfn, 'r') as fp_:
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
    try:
        with salt.utils.fopen(cache_file, 'w+') as fp_:
            serial.dump(ret, fp_)
    except (IOError, OSError):
        msg = 'Unable to write to "state.sls" cache file {0}'
        log.error(msg.format(cache_file))
    _set_retcode(ret)
    with open(cfn, 'w+') as fp_:
        try:
            serial.dump(high_, fp_)
        except TypeError:
            # Can't serialize pydsl
            pass
    return ret


def top(topfn, test=None, **kwargs):
    '''
    Execute a specific top file instead of the default

    CLI Example::

        salt '*' state.top reverse_top.sls

        salt '*' state.top reverse_top.sls exclude=sls_to_exclude
        salt '*' state.top reverse_top.sls exclude="[{'id': 'id_to_exclude'}, {'sls': 'sls_to_exclude'}]"
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    if salt.utils.test_mode(test=test, **kwargs):
        __opts__['test'] = True
    else:
        __opts__['test'] = __opts__.get('test', None)
    st_ = salt.state.HighState(__opts__)
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
    return ret


def show_highstate():
    '''
    Retrieve the highstate data from the salt master and display it

    CLI Example::

        salt '*' state.show_highstate
    '''
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


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example::

        salt '*' state.show_lowstate
    '''
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
    if isinstance(ret, list):
        __context__['retcode'] = 1
    return ret


def show_sls(mods, env='base', test=None, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example::

        salt '*' state.show_sls core,edit.vim dev
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    opts = copy.copy(__opts__)
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
    return high_


def show_top():
    '''
    Return the top data that the minion will use for a highstate

    CLI Example::

        salt '*' state.show_top
    '''
    conflict = running()
    if conflict:
        __context__['retcode'] = 1
        return conflict
    st_ = salt.state.HighState(__opts__)
    ret = {}
    static = st_.get_top()
    ext = st_.client.ext_nodes()
    for top_ in [static, ext]:
        for env in top_:
            if env not in ret:
                ret[env] = top_[env]
            else:
                for match in top_[env]:
                    if match not in ret[env]:
                        ret[env][match] = top_[env][match]
                    else:
                        ret[env][match].extend(top_[env][match])
    return ret

# Just commenting out, someday I will get this working
#def show_masterstate():
#    '''
#    Display the data gathered from the master compiled state
#
#    CLI Example::
#
#        salt '*' state.show_masterstate
#    '''
#    st_ = salt.state.RemoteHighState(__opts__, __grains__)
#    return st_.compile_master()


def single(fun, name, test=None, **kwargs):
    '''
    Execute a single state function with the named kwargs, returns False if
    insufficient data is sent to the command

    By default, the values of the kwargs will be parsed as YAML. So, you can
    specify lists values, or lists of single entry key-value maps, as you
    would in a YAML salt file. Alternatively, JSON format of keyword values
    is also supported.

    CLI Example::

        salt '*' state.single pkg.installed name=vim

    '''
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
    opts = copy.copy(__opts__)
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
    return ret


def clear_cache():
    '''
    Clear out cached state files, forcing even cache runs to refresh the cache
    on the next state execution.

    Remember that the state cache is completely disabled by default, this
    execution only applies if cache=True is used in states

    CLI Example::

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
