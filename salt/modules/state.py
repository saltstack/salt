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


def __resolve_struct(value, kwval_as):
    '''
    Take a string representing a structure and safely serialize it with the
    specified medium
    '''
    if kwval_as == 'yaml':
        return  _yaml_load(value, _YamlCustomLoader)
    elif kwval_as == 'json':
        return json.loads(value)
    elif kwval_as is None or kwval_as == 'verbatim':
        return value


def _filter_running(running):
    '''
    Filter out the result: True + no changes data
    '''
    ret = {}
    for tag in running:
        if running[tag]['result']:
            # It is true
            if running[tag]['changes']:
                # It is blue
                ret[tag] = running[tag]
                continue
        else:
            ret[tag] = running[tag]
    return ret


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
        return conflict
    st_ = salt.state.State(__opts__)
    err = st_.verify_data(data)
    if err:
        return err
    return st_.call(data)


def high(data):
    '''
    Execute the compound calls stored in a single set of high data
    This function is mostly intended for testing the state system

    CLI Example::

        salt '*' state.high '{"vim": {"pkg": ["installed"]}}'
    '''
    conflict = running()
    if conflict:
        return conflict
    st_ = salt.state.State(__opts__)
    return st_.call_high(data)


def template(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example::

        salt '*' state.template '<Path to template on the minion>'
    '''
    conflict = running()
    if conflict:
        return conflict
    st_ = salt.state.State(__opts__)
    return st_.call_template(tem)


def template_str(tem):
    '''
    Execute the information stored in a string from an sls template

    CLI Example::

        salt '*' state.template_str '<Template String>'
    '''
    conflict = running()
    if conflict:
        return conflict
    st_ = salt.state.State(__opts__)
    return st_.call_template_str(tem)


def highstate(test=None, **kwargs):
    '''
    Retrive the state data from the salt master for this minion and execute it

    CLI Example::

        salt '*' state.highstate
    '''
    conflict = running()
    if conflict:
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    opts = copy.copy(__opts__)

    if not test is None:
        opts['test'] = test
    else:
        opts['test'] = None

    pillar = __resolve_struct(
            kwargs.get('pillar', ''),
            kwargs.get('kwval_as', 'yaml'))

    st_ = salt.state.HighState(opts, pillar)
    st_.push_active()
    try:
        ret = st_.call_highstate(exclude=kwargs.get('exclude', []))
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

    return ret


def sls(mods, env='base', test=None, exclude=None, **kwargs):
    '''
    Execute a set list of state modules from an environment, default
    environment is base

    CLI Example::

        salt '*' state.sls core,edit.vim dev
    '''
    conflict = running()
    if conflict:
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    opts = copy.copy(__opts__)

    if not test is None:
        opts['test'] = test
    else:
        opts['test'] = None

    pillar = __resolve_struct(
            kwargs.get('pillar', ''),
            kwargs.get('kwval_as', 'yaml'))

    st_ = salt.state.HighState(opts, pillar)

    if isinstance(mods, string_types):
        mods = mods.split(',')

    st_.push_active()
    try:
        high, errors = st_.render_highstate({env: mods})

        if errors:
            return errors

        if exclude:
            if isinstance(exclude, str):
                exclude = exclude.split(',')
            if '__exclude__' in high:
                high['__exclude__'].extend(exclude)
            else:
                high['__exclude__'] = exclude
        ret = st_.state.call_high(high)
    finally:
        st_.pop_active()
    if __salt__['config.option']('state_data', '') == 'terse' or kwargs.get('terse'):
        ret = _filter_running(ret)
    serial = salt.payload.Serial(__opts__)
    cache_file = os.path.join(__opts__['cachedir'], 'sls.p')
    try:
        with salt.utils.fopen(cache_file, 'w+') as fp_:
            serial.dump(ret, fp_)
    except (IOError, OSError):
        msg = 'Unable to write to "state.sls" cache file {0}'
        log.error(msg.format(cache_file))
    return ret


def top(topfn):
    '''
    Execute a specific top file instead of the default

    CLI Example::

        salt '*' state.top reverse_top.sls
    '''
    conflict = running()
    if conflict:
        return conflict
    if not _check_pillar(kwargs):
        __context__['retcode'] = 5
        err = ['Pillar failed to render with the following messages:']
        err += __pillar__['_errors']
        return err
    if salt.utils.test_mode(test=test, **kwargs):
        opts['test'] = True
    else:
        opts['test'] = None
    st_ = salt.state.HighState(__opts__)
    st_.push_active()
    st_.opts['state_top'] = os.path.join('salt://', topfn)
    try:
        return st_.call_highstate()
    finally:
        st_.pop_active()


def show_highstate():
    '''
    Retrieve the highstate data from the salt master and display it

    CLI Example::

        salt '*' state.show_highstate
    '''
    st_ = salt.state.HighState(__opts__)
    return st_.compile_highstate()


def show_lowstate():
    '''
    List out the low data that will be applied to this minion

    CLI Example::

        salt '*' state.show_lowstate
    '''
    st_ = salt.state.HighState(__opts__)
    return st_.compile_low_chunks()


def show_sls(mods, env='base', test=None, **kwargs):
    '''
    Display the state data from a specific sls or list of sls files on the
    master

    CLI Example::

        salt '*' state.show_sls core,edit.vim dev
    '''
    opts = copy.copy(__opts__)
    if not test is None:
        opts['test'] = test
    else:
        opts['test'] = None
    st_ = salt.state.HighState(opts)
    if isinstance(mods, string_types):
        mods = mods.split(',')
    high, errors = st_.render_highstate({env: mods})
    errors += st_.state.verify_high(high)
    if errors:
        return errors
    return high


def show_top():
    '''
    Return the top data that the minion will use for a highstate

    CLI Example::

        salt '*' state.show_top
    '''
    st_ = salt.state.HighState(__opts__)
    ret = {}
    static = st_.get_top()
    ext = st_.client.ext_nodes()
    for top in [static, ext]:
        for env in top:
            if not env in ret:
                ret[env] = top[env]
            else:
                for match in top[env]:
                    if not match in ret[env]:
                        ret[env][match] = top[env][match]
                    else:
                        ret[env][match].extend(top[env][match])
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


def single(fun, name, test=None, kwval_as='yaml', **kwargs):
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
        return conflict
    comps = fun.split('.')
    if len(comps) < 2:
        return 'Invalid function passed'
    kwargs.update({'state': comps[0],
                   'fun': comps[1],
                   '__id__': name,
                   'name': name})
    opts = copy.copy(__opts__)
    if not test is None:
        opts['test'] = test
    else:
        opts['test'] = None
    st_ = salt.state.State(opts)
    err = st_.verify_data(kwargs)
    if err:
        return err

    if kwval_as == 'yaml':
        def parse_kwval(value):
            return _yaml_load(value, _YamlCustomLoader)
    elif kwval_as == 'json':
        def parse_kwval(value):
            return json.loads(value)
    elif kwval_as is None or kwval_as == 'verbatim':
        parse_kwval = lambda value: value
    else:
        return 'Unknown format({0}) for state keyword arguments!'.format(
                kwval_as)

    for key, value in kwargs.iteritems():
        if not key.startswith('__pub_'):
            kwargs[key] = parse_kwval(value)

    return {'{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(kwargs):
            st_.call(kwargs)}
