# -*- coding: utf-8 -*-
'''
Control the Salt command interface
==================================

This state is intended for use from the Salt Master. It provides access to
sending commands down to minions as well as access to executing master-side
modules. These state functions wrap Salt's :ref:`Python API <python-api>`.

.. seealso:: More Orchestrate documentation

    * :ref:`Full Orchestrate Tutorial <orchestrate-runner>`
    * :py:func:`The Orchestrate runner <salt.runners.state.orchestrate>`
'''
from __future__ import absolute_import

# Import python libs
import fnmatch
import logging
import time

# Import salt libs
import salt.syspaths
import salt.utils
import salt.utils.event
import salt.ext.six as six
from salt.ext.six import string_types

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
        top=None,
        env=None,
        test=False,
        pillar=None,
        expect_minions=False,
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

    top
        Should be the name of a top file. If set state.top is called with this
        top file instead of state.sls.

    sls
        A group of sls files to execute. This can be defined as a single string
        containing a single sls file, or a list of sls files

    test
        Pass ``test=true`` through to the state function

    pillar
        Pass the ``pillar`` kwarg through to the state function

    saltenv
        The default salt environment to pull sls files from

    ssh
        Set to `True` to use the ssh client instead of the standard salt client

    roster
        In the event of using salt-ssh, a roster system can be set

    expect_minions
        An optional boolean for failing if some minions do not respond

    fail_minions
        An optional list of targeted minions where failure is an option

    allow_fail
        Pass in the number of minions to allow for failure before setting
        the result of the execution to False

    concurrent
        Allow multiple state runs to occur at once.

        WARNING: This flag is potentially dangerous. It is designed
        for use when multiple state runs can safely be run at the same
        Do not use this flag for performance optimization.

    Examples:

    Run a list of sls files via :py:func:`state.sls <salt.state.sls>` on target
    minions:

    .. code-block:: yaml

        webservers:
          salt.state:
            - tgt: 'web*'
            - sls:
              - apache
              - django
              - core
            - saltenv: prod

    Run a full :py:func:`state.highstate <salt.state.highstate>` on target
    mininons.

    .. code-block:: yaml

        databases:
          salt.state:
            - tgt: role:database
            - tgt_type: grain
            - highstate: True
    '''
    cmd_kw = {'arg': [], 'kwarg': {}, 'ret': ret, 'timeout': timeout}

    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}

    try:
        allow_fail = int(allow_fail)
    except ValueError:
        ret['result'] = False
        ret['comment'] = 'Passed invalid value for \'allow_fail\', must be an int'
        return ret

    if env is not None:
        msg = (
            'Passing a salt environment should be done using \'saltenv\' not '
            '\'env\'. This warning will go away in Salt Boron and this '
            'will be the default and expected behavior. Please update your '
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
    cmd_kw['expect_minions'] = expect_minions
    if highstate:
        fun = 'state.highstate'
    elif top:
        fun = 'state.top'
        cmd_kw['arg'].append(top)
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

    if pillar:
        cmd_kw['kwarg']['pillar'] = pillar

    cmd_kw['kwarg']['saltenv'] = __env__

    if isinstance(concurrent, bool):
        cmd_kw['kwarg']['concurrent'] = concurrent
    else:
        ret['comment'] = ('Must pass in boolean for value of \'concurrent\'')
        ret['result'] = False
        return ret

    if __opts__['test'] is True:
        ret['comment'] = (
                '{0} will be run on target {1} as test={2}'
                ).format(fun == 'state.highstate' and 'Highstate'
                    or 'States '+','.join(cmd_kw['arg']),
                tgt, str(test))
        ret['result'] = None
        return ret
    cmd_ret = __salt__['saltutil.cmd'](tgt, fun, **cmd_kw)

    changes = {}
    fail = set()
    failures = {}
    no_change = set()

    if fail_minions is None:
        fail_minions = ()
    elif isinstance(fail_minions, string_types):
        fail_minions = [minion.strip() for minion in fail_minions.split(',')]
    elif not isinstance(fail_minions, list):
        ret.setdefault('warnings', []).append(
            '\'fail_minions\' needs to be a list or a comma separated '
            'string. Ignored.'
        )
        fail_minions = ()

    for minion, mdata in six.iteritems(cmd_ret):
        if mdata.get('out', '') != 'highstate':
            log.warning("Output from salt state not highstate")

        m_ret = False

        if 'return' in mdata and 'ret' not in mdata:
            mdata['ret'] = mdata.pop('return')

        if mdata.get('failed', False):
            m_state = False
        else:
            m_ret = mdata['ret']
            m_state = salt.utils.check_state_result(m_ret)

        if not m_state:
            if minion not in fail_minions:
                fail.add(minion)
            failures[minion] = m_ret and m_ret or 'Minion did not respond'
            continue
        for state_item in six.itervalues(m_ret):
            if state_item['changes']:
                changes[minion] = m_ret
                break
        else:
            no_change.add(minion)

    if changes:
        ret['changes'] = {'out': 'highstate', 'ret': changes}
    if len(fail) > allow_fail:
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
        for minion, failure in six.iteritems(failures):
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
        expect_minions=False,
        fail_minions=None,
        fail_function=None,
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

    expect_minions
        An optional boolean for failing if some minions do not respond

    fail_minions
        An optional list of targeted minions where failure is an option

    fail_function
        An optional string that points to a salt module that returns True or False
        based on the returned data dict for individual minions

    ssh
        Set to `True` to use the ssh client instead of the standard salt client
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if kwarg is None:
        kwarg = {}
    if isinstance(arg, str):
        ret['warnings'] = ['Please specify \'arg\' as a list, not a string. '
                           'Modifying in place, but please update SLS file '
                           'to remove this warning.']
        arg = arg.split()

    cmd_kw = {'arg': arg or [], 'kwarg': kwarg, 'ret': ret, 'timeout': timeout}

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
    cmd_kw['expect_minions'] = expect_minions
    cmd_kw['_cmd_meta'] = True
    fun = name
    if __opts__['test'] is True:
        ret['comment'] = (
                'Function {0} will be executed on target {1} as test={2}'
                ).format(fun, tgt, str(False))
        ret['result'] = None
        return ret
    try:
        cmd_ret = __salt__['saltutil.cmd'](tgt, fun, **cmd_kw)
    except Exception as exc:
        ret['result'] = False
        ret['comment'] = str(exc)
        return ret

    changes = {}
    fail = set()
    failures = {}

    if fail_minions is None:
        fail_minions = ()
    elif isinstance(fail_minions, string_types):
        fail_minions = [minion.strip() for minion in fail_minions.split(',')]
    elif not isinstance(fail_minions, list):
        ret.setdefault('warnings', []).append(
            '\'fail_minions\' needs to be a list or a comma separated '
            'string. Ignored.'
        )
        fail_minions = ()
    for minion, mdata in six.iteritems(cmd_ret):
        m_ret = False
        if mdata.get('retcode'):
            ret['result'] = False
            fail.add(minion)
        if mdata.get('failed', False):
            m_func = False
        else:
            if 'return' in mdata and 'ret' not in mdata:
                mdata['ret'] = mdata.pop('return')
            m_ret = mdata['ret']
            m_func = (not fail_function and True) or __salt__[fail_function](m_ret)

        if not m_func:
            if minion not in fail_minions:
                fail.add(minion)
            failures[minion] = m_ret and m_ret or 'Minion did not respond'
            continue
        changes[minion] = m_ret
    if not cmd_ret:
        ret['result'] = False
        ret['command'] = 'No minions responded'
    else:
        if changes:
            ret['changes'] = {'out': 'highstate', 'ret': changes}
        if fail:
            ret['result'] = False
            ret['comment'] = 'Running function {0} failed on minions: {1}'.format(name, ', '.join(fail))
        else:
            ret['comment'] = 'Function ran successfully.'
        if changes:
            ret['comment'] += ' Function {0} ran on {1}.'.format(name, ', '.join(changes))
        if failures:
            ret['comment'] += '\nFailures:\n'
            for minion, failure in six.iteritems(failures):
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


def wait_for_event(
        name,
        id_list,
        event_id='id',
        timeout=300):
    '''
    Watch Salt's event bus and block until a condition is met

    .. versionadded:: 2014.7.0

    name
        An event tag to watch for; supports Reactor-style globbing.
    id_list
        A list of event identifiers to watch for -- usually the minion ID. Each
        time an event tag is matched the event data is inspected for
        ``event_id``, if found it is removed from ``id_list``. When ``id_list``
        is empty this function returns success.
    event_id : id
        The name of a key in the event data. Default is ``id`` for the minion
        ID, another common value is ``name`` for use with orchestrating
        salt-cloud events.
    timeout : 300
        The maximum time in seconds to wait before failing.

    The following example blocks until all the listed minions complete a
    restart and reconnect to the Salt master:

    .. code-block:: yaml

        reboot_all_minions:
          salt.function:
            - name: system.reboot
            - tgt: '*'

        wait_for_reboots:
          salt.wait_for_event:
            - name: salt/minion/*/start
            - id_list:
              - jerry
              - stuart
              - dave
              - phil
              - kevin
              - mike
            - require:
              - salt: reboot_all_minions
    '''
    ret = {'name': name, 'changes': {}, 'comment': '', 'result': False}

    sevent = salt.utils.event.get_event(
            'master',
            __opts__['sock_dir'],
            __opts__['transport'],
            opts=__opts__)

    del_counter = 0
    starttime = time.time()
    timelimit = starttime + timeout
    while True:
        event = sevent.get_event(full=True)
        is_timedout = time.time() > timelimit

        if event is None and not is_timedout:
            log.trace("wait_for_event: No event data; waiting.")
            continue
        elif event is None and is_timedout:
            ret['comment'] = 'Timeout value reached.'
            return ret

        if fnmatch.fnmatch(event['tag'], name):
            val = event['data'].get(event_id)

            if val is not None:
                try:
                    val_idx = id_list.index(val)
                except ValueError:
                    log.trace("wait_for_event: Event identifier '{0}' not in "
                            "id_list; skipping.".format(event_id))
                else:
                    del id_list[val_idx]
                    del_counter += 1
                    minions_seen = ret['changes'].setdefault('minions_seen', [])
                    minions_seen.append(val)

                    log.debug("wait_for_event: Event identifier '{0}' removed "
                            "from id_list; {1} items remaining."
                            .format(val, len(id_list)))
            else:
                log.trace("wait_for_event: Event identifier '{0}' not in event "
                        "'{1}'; skipping.".format(event_id, event['tag']))
        else:
            log.debug("wait_for_event: Skipping unmatched event '{0}'"
                    .format(event['tag']))

        if len(id_list) == 0:
            ret['result'] = True
            ret['comment'] = 'All events seen in {0} seconds.'.format(
                    time.time() - starttime)
            return ret

        if is_timedout:
            ret['comment'] = 'Timeout value reached.'
            return ret


def runner(name, **kwargs):
    '''
    Execute a runner module on the master

    .. versionadded:: 2014.7.0

    name
        The name of the function to run
    kwargs
        Any keyword arguments to pass to the runner function

    .. code-block:: yaml

         run-manage-up:
          salt.runner:
            - name: manage.up
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}
    out = __salt__['saltutil.runner'](name, **kwargs)

    ret['result'] = True
    ret['comment'] = "Runner function '{0}' executed.".format(name)

    if out:
        ret['changes'] = out

    return ret


def wheel(name, **kwargs):
    '''
    Execute a wheel module on the master

    .. versionadded:: 2014.7.0

    name
        The name of the function to run
    kwargs
        Any keyword arguments to pass to the wheel function

    .. code-block:: yaml

        accept_minion_key:
          salt.wheel:
            - name: key.accept
            - match: frank
    '''
    ret = {'name': name, 'result': False, 'changes': {}, 'comment': ''}
    out = __salt__['saltutil.wheel'](name, **kwargs)

    ret['result'] = True
    ret['comment'] = "Wheel function '{0}' executed.".format(name)

    if out:
        ret['changes'] = out

    return ret
