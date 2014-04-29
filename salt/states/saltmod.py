# -*- coding: utf-8 -*-
'''
Control the Salt command interface
==================================

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
        - saltenv: prod

    databases:
      salt.state:
        - tgt: role:database
        - tgt_type: grain
        - highstate: True
'''

# Import python libs
import logging

# Import salt libs
import salt.utils
import salt._compat

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'salt'


def __virtual__():
    '''
    Named salt
    '''
    return __virtualname__


def state(
        name,
        tgt,
        ssh=False,
        tgt_type=None,
        expr_form=None,
        ret='',
        highstate=None,
        sls=None,
        env=None,
        test=False,
        fail_minions=None,
        allow_fail=0,
        concurrent=False,
        timeout=None):
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

    saltenv
        The default salt environment to pull sls files from

    ssh
        Set to `True` to use the ssh client instaed of the standard salt client

    roster
        In the event of using salt-ssh, a roster system can be set

    fail_minions
        An optional list of targeted minions where failure is an option

    concurrent
        Allow multiple state runs to occur at once.

        WARNING: This flag is potentially dangerous. It is designed
        for use when multiple state runs can safely be run at the same
        Do not use this flag for performance optimization.
    '''
    cmd_kw = {'arg': [], 'kwarg': {}, 'ret': ret, 'timeout': timeout}

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}

    if env is not None:
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behaviour. Please update your '
            'state files.'
        )
        salt.utils.warn_until('Boron', msg)
        ret.setdefault('warnings', []).append(msg)
        # No need to set __env__ = env since that's done in the state machinery

    if expr_form and tgt_type:
        ret.setdefault('warnings', []).append(
            'Please only use \'tgt_type\' or \'expr_form\' not both. '
            'Preferring \'tgt_type\' over \'expr_form\''
        )
        expr_form = None
    elif expr_form and not tgt_type:
        tgt_type = expr_form
    elif not tgt_type and not expr_form:
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
        cmd_kw['kwarg']['test'] = test

    cmd_kw['kwarg']['saltenv'] = __env__

    if isinstance(concurrent, bool):
        cmd_kw['kwarg']['concurrent'] = concurrent
    else:
        ret['comment'] = ('Must pass in boolean for value of \'concurrent\'')
        ret['result'] = False
        return ret

    if __opts__['test'] is True:
        ret['comment'] = (
                'State run to be executed on target {0} as test={1}'
                ).format(tgt, str(test))
        ret['result'] = None
        return ret
    cmd_ret = __salt__['saltutil.cmd'](tgt, fun, **cmd_kw)

    changes = {}
    fail = set()
    failures = {}
    no_change = set()

    if fail_minions is None:
        fail_minions = ()
    elif isinstance(fail_minions, salt._compat.string_types):
        fail_minions = [minion.strip() for minion in fail_minions.split(',')]
    elif not isinstance(fail_minions, list):
        ret.setdefault('warnings', []).append(
            '\'fail_minions\' needs to be a list or a comma separated '
            'string. Ignored.'
        )
        fail_minions = ()

    for minion, mdata in cmd_ret.iteritems():
        if mdata['out'] != 'highstate':
            log.warning("Output from salt state not highstate")
        m_ret = mdata['ret']
        m_state = salt.utils.check_state_result(m_ret)

        if not m_state:
            if minion not in fail_minions:
                fail.add(minion)
            failures[minion] = m_ret
            continue
        for state_item in m_ret.itervalues():
            if state_item['changes']:
                changes[minion] = m_ret
                break
        else:
            no_change.add(minion)

    if changes:
        ret['changes'] = {'out': 'highstate', 'ret': changes}
    if fail:
        ret['result'] = False
        ret['comment'] = 'Run failed on minions: {0}'.format(', '.join(fail))
    else:
        ret['comment'] = 'States ran successfully.'
        if changes:
            ret['comment'] += ' Updating {0}.'.format(', '.join(changes))
        if no_change:
            ret['comment'] += ' No changes made to {0}.'.format(', '.join(no_change))
    if failures:
        ret['comment'] += '\nFailures:\n'
        for minion, failure in failures.iteritems():
            ret['comment'] += '\n'.join(
                    (' ' * 4 + l)
                    for l in salt.output.out_format(
                        {minion: failure},
                        'highstate',
                        __opts__,
                        ).splitlines()
                    )
            ret['comment'] += '\n'
    return ret


def function(
        name,
        tgt,
        ssh=False,
        tgt_type=None,
        expr_form=None,
        ret='',
        fail_minions=None,
        arg=None,
        kwarg=None,
        timeout=None):
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

    kwarg
        The list of keyword arguments to pass into the function

    ret
        Optionally set a single or a list of returners to use

    fail_minions
        An optional list of targeted minions where failure is an option

    ssh
        Set to `True` to use the ssh client instaed of the standard salt client
    '''
    if kwarg is None:
        kwarg = {}

    cmd_kw = {'arg': arg or [], 'kwarg': kwarg, 'ret': ret, 'timeout': timeout}

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}

    if expr_form and tgt_type:
        ret['warnings'] = [
            'Please only use \'tgt_type\' or \'expr_form\' not both. '
            'Preferring \'tgt_type\' over \'expr_form\''
        ]
        expr_form = None
    elif expr_form and not tgt_type:
        tgt_type = expr_form
    elif not tgt_type and not expr_form:
        tgt_type = 'glob'

    cmd_kw['expr_form'] = tgt_type
    cmd_kw['ssh'] = ssh
    fun = name
    cmd_ret = __salt__['saltutil.cmd'](tgt, fun, **cmd_kw)
    
    changes = {}
    fail = set()
    failures = {}
    no_change = set()

    if fail_minions is None:
        fail_minions = ()
    elif isinstance(fail_minions, salt._compat.string_types):
        fail_minions = [minion.strip() for minion in fail_minions.split(',')]
    elif not isinstance(fail_minions, list):
        ret.setdefault('warnings', []).append(
            '\'fail_minions\' needs to be a list or a comma separated '
            'string. Ignored.'
        )
        fail_minions = ()

    for minion, mdata in cmd_ret.iteritems():
        m_ret = mdata['ret']
        m_state = _check_func_result(m_ret)

        if not m_state:
            if minion not in fail_minions:
                fail.add(minion)
            failures[minion] = m_ret
            continue
        for state_item in m_ret.itervalues():
            changes[minion] = m_ret
            
    if changes:
        ret['changes'] = {'out': 'highstate', 'ret': changes}
    if fail:
        ret['result'] = False
        ret['comment'] = 'Run failed on minions: {0}'.format(', '.join(fail))
    else:
        ret['comment'] = 'Functions ran successfully.'
        if changes:
            ret['comment'] += ' Functions ran on {0}.'.format(', '.join(changes))
    if failures:
        ret['comment'] += '\nFailures:\n'
        for minion, failure in failures.iteritems():
            ret['comment'] += '\n'.join(
                    (' ' * 4 + l)
                    for l in salt.output.out_format(
                        {minion: failure},
                        'highstate',
                        __opts__,
                        ).splitlines()
                    )
            ret['comment'] += '\n'
    return ret

def _check_func_result(running):
    '''
    Check the total return value of the run and determine if the running
    dict has any issues
    '''
    if not isinstance(running, dict):
        return False

    if not running:
        return False

    for state_result in running.itervalues():
        if not isinstance(state_result, dict):
            # return false when hosts return a list instead of a dict
            return False

        if 'result' in state_result:
            if state_result.get('result', False) is False:
                return False
        return True

    return True
