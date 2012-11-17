'''
Control the state system on the minion
'''

# Import Python libs
import os
import copy
import logging

# Import Salt libs
import salt.utils
import salt.state
import salt.payload
from salt.utils.yaml import load as yaml_load
from salt.utils.yaml import CustomLoader as YamlCustomLoader
import json
from salt._compat import string_types


__outputter__ = {
    'sls': 'highstate',
    'top': 'highstate',
    'single': 'highstate',
    'highstate': 'highstate',
}

log = logging.getLogger(__name__)


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
               '{2} ').format(
                data['fun'],
                data['pid'],
                salt.utils.jid_to_time(data['jid']),
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
    salt.utils.daemonize_if(__opts__, **kwargs)
    opts = copy.copy(__opts__)

    if not test is None:
        opts['test'] = test

    st_ = salt.state.HighState(opts)
    ret = st_.call_highstate()
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


def sls(mods, env='base', test=None, **kwargs):
    '''
    Execute a set list of state modules from an environment, default
    environment is base

    CLI Example::

        salt '*' state.sls core,edit.vim dev
    '''
    conflict = running()
    if conflict:
        return conflict
    opts = copy.copy(__opts__)

    if not test is None:
        opts['test'] = test

    salt.utils.daemonize_if(opts, **kwargs)
    st_ = salt.state.HighState(opts)

    if isinstance(mods, string_types):
        mods = mods.split(',')

    high, errors = st_.render_highstate({env: mods})

    if errors:
        return errors

    ret = st_.state.call_high(high)
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
    st_ = salt.state.HighState(__opts__)
    st_.opts['state_top'] = os.path.join('salt://', topfn)
    return st_.call_highstate()


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
    salt.utils.daemonize_if(opts, **kwargs)
    st_ = salt.state.HighState(opts)
    if isinstance(mods, string_types):
        mods = mods.split(',')
    high, errors = st_.render_highstate({env: mods})
    errors += st_.state.verify_high(high)
    if errors:
        return errors
    return high


def show_masterstate():
    '''
    Display the data gathered from the master compiled state

    CLI Example::

        salt '*' state.show_masterstate
    '''
    st_ = salt.state.RemoteHighState(__opts__, __grains__)
    return st_.compile_master()


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
    st_ = salt.state.State(opts)
    err = st_.verify_data(kwargs)
    if err:
        return err

    if kwval_as == 'yaml':
        def parse_kwval(value):
            return yaml_load(value, YamlCustomLoader)
    elif kwval_as == 'json':
        def parse_kwval(value):
            return json.loads(value)
    else:
        return 'Unknown format({0}) for state keyword arguments!'.format(
                kwval_as)

    for key, value in kwargs.iteritems():
        if not key.startswith('__pub_'):
            kwargs[key] = parse_kwval(value)

    return {'{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(kwargs):
            st_.call(kwargs)}
