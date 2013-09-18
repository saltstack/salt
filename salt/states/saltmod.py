# -*- coding: utf-8 -*-
'''
The Salt state is used to control the salt command interface. This state is
intended for use primarily from the state runner from the master.

The salt.state declaration can call out a highstate or a list of sls:

    webservers:
      salt.state:
        - tgt: 'web*'
        - sls:
          - apache
          - django
          - core
        - env: prod

    databasees:
      salt.state:
        - tgt: role:database
        - tgt_type: grain
        - highstate: True
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Named salt
    '''
    return 'salt'


def state(
        name,
        tgt,
        ssh=False,
        tgt_type=None,
        ret='',
        highstate=None,
        sls=None,
        env=None,
        test=False,
        fail_minions='',
        allow_fail=0,
        **kwargs):
    '''
    Invoke a state run on a given target

    name
        An arbitrary name used to track the state execution

    tgt
        The target specification for the state run.

    tgt_type | expr_form
        The target type to resolve, defaults to glob

    ret
        Optionally set a single or a list of returners to use

    highstate
        Defaults to None, if set to True the target systems will ignore any
        sls references specified in the sls option and call state.highstate
        on the targeted minions

    sls
        A group of sls files to execute. This can be defined as a single string
        containing a single sls file, or a list of sls files

    env
        The default environment to pull sls files from

    ssh
        Set to `True` to use the ssh client instaed of the standard salt client

    roster
        In the event of using salt-ssh, a roster system can be set

    fail_minions
        An optional list of targeted minions where failure is an option
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    cmd_kw = {'arg': []}
    if 'expr_form' in kwargs and not tgt_type:
        tgt_type = kwargs['expr_form']
    if not tgt_type:
        tgt_type = 'glob'
    cmd_kw['expr_form'] = tgt_type
    cmd_kw['ssh'] = ssh
    if highstate:
        fun = 'state.highstate'
    elif sls:
        fun = 'state.sls'
        if isinstance(sls, list):
            sls = ','.join(sls)
        cmd_kw['arg'].append(sls)
    else:
        ret['comment'] = 'No highstate or sls specified, no execution made'
        ret['result'] = False
        return ret
    if test:
        cmd_kw['arg'].append('test={0}'.format(test))
    if env:
        cmd_kw['arg'].append('env={0}'.format(env))
    if ret:
        cmd_kw['ret'] = ret
    if __opts__['test'] is True:
        ret['comment'] = (
                'State run to be executed on target {0} as test={1}'
                ).format(tgt, str(test))
        ret['result'] = None
        return ret
    cmd_ret = __salt__['saltutil.cmd'](tgt, fun, **cmd_kw)
    ret['changes'] = cmd_ret
    fail = set()
    if isinstance(fail_minions, str):
        fail_minions = [fail_minions]
    for minion, m_ret in cmd_ret.items():
        if minion in fail_minions:
            continue
        m_state = salt.utils.check_state_result(m_ret)
        if not m_state:
            fail.add(minion)
    if fail:
        ret['result'] = False
        ret['comment'] = 'Run failed on minions: {0}'.format(', '.join(fail))
        return ret
    ret['comment'] = 'States ran successfully on {0}'.format(
            ', '.join(cmd_ret))
    return ret


def function(
        name,
        tgt,
        ssh=False,
        tgt_type=None,
        ret='',
        arg=(),
        **kwargs):
    '''
    Execute a single module function on a remote minion via salt or salt-ssh

    name
        The name of the function to run, aka cmd.run or pkg.install

    tgt
        The target specification, aka '*' for all minions

    tgt_type | expr_form
        The target type, defaults to glob

    arg
        The list of arguments to pass into the function

    ret
        Optionally set a single or a list of returners to use

    ssh
        Set to `True` to use the ssh client instaed of the standard salt client
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    cmd_kw = {'arg': []}
    if 'expr_form' in kwargs and not tgt_type:
        tgt_type = kwargs['expr_form']
    if not tgt_type:
        tgt_type = 'glob'
    cmd_kw['expr_form'] = tgt_type
    cmd_kw['ssh'] = ssh
    fun = name
    if ret:
        cmd_kw['ret'] = ret
    cmd_ret = __salt__['saltutil.cmd'](tgt, fun, **cmd_kw)
    ret['changes'] = cmd_ret
    ret['comment'] = 'Function {0} ran successfully on {0}'.format(
            ', '.join(cmd_ret))
    return ret
