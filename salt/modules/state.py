'''
Control the state system on the minion
'''

# Import Python libs
import copy
import os

# Import Salt libs
import salt.state
import salt.payload
from salt._compat import string_types

__outputter__ = {
                 'highstate': 'highstate',
                 'sls': 'highstate',
                 'top': 'highstate',
                 'single': 'highstate',
                 }


def low(data):
    '''
    Execute a single low data call
    This function is mostly intended for testing the state system

    CLI Example::

        salt '*' state.low '{"state": "pkg", "fun": "installed", "name": "vi"}'
    '''
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
    st_ = salt.state.State(__opts__)
    return st_.call_high(data)


def template(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example::

        salt '*' state.template '<Path to template on the minion>'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template(tem)


def template_str(tem):
    '''
    Execute the information stored in a template file on the minion

    CLI Example::

        salt '*' state.template_str '<Template String>'
    '''
    st_ = salt.state.State(__opts__)
    return st_.call_template_str(tem)


def highstate(test=None, **kwargs):
    '''
    Retrive the state data from the salt master for this minion and execute it

    CLI Example::

        salt '*' state.highstate
    '''
    salt.utils.daemonize_if(__opts__, **kwargs)
    opts = copy.copy(__opts__)
    if not test is None:
        opts['test'] = test
    st_ = salt.state.HighState(opts)
    ret = st_.call_highstate()
    serial = salt.payload.Serial(__opts__)
    with open(os.path.join(__opts__['cachedir'], 'highstate.p'), 'w+') as fp_:
        serial.dump(ret, fp_)
    return ret


def sls(mods, env='base', test=None, **kwargs):
    '''
    Execute a set list of state modules from an environment, default
    environment is base

    CLI Example::

        salt '*' state.sls core,edit.vim dev
    '''
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
    with open(os.path.join(__opts__['cachedir'], 'sls.p'), 'w+') as fp_:
        serial.dump(ret, fp_)
    return ret


def top(topfn):
    '''
    Execute a specific top file instead of the default

    CLI Example::

        salt '*' state.top reverse_top.sls
    '''
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

        salt '*' state.sls core,edit.vim dev
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


def single(fun=None, test=None, **kwargs):
    '''
    Execute a single state function with the named kwargs, returns False if
    insufficient data is sent to the command

    CLI Example::

        salt '*' state.single pkg.installed name=vim
    '''
    if not 'name' in kwargs:
        return False
    if fun:
        comps = fun.split('.')
        if len(comps) < 2:
            return False
    else:
        return False
    kwargs.update({'state': comps[0],
                   'fun': comps[1],
                   '__id__': kwargs['name']})
    opts = copy.copy(__opts__)
    if not test is None:
        opts['test'] = test
    st_ = salt.state.State(opts)
    err = st_.verify_data(kwargs)
    if err:
        return err
    return {'{0[state]}_|-{0[__id__]}_|-{0[name]}_|-{0[fun]}'.format(kwargs):
            st_.call(kwargs)}
