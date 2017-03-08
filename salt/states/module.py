# -*- coding: utf-8 -*-
r'''
Execution of Salt modules from within states
============================================

Here you have two options: `module.run` and `module.xrun`.

With `module.run` these states allow individual execution module calls to be
made via states. To call a single module function use a :mod:`module.run <salt.states.module.run>`
state:

.. code-block:: yaml

    mine.send:
      module.run:
        - name: network.interfaces

Note that this example is probably unnecessary to use in practice, since the
``mine_functions`` and ``mine_interval`` config parameters can be used to
schedule updates for the mine (see :ref:`here <salt-mine>` for more
info).

It is sometimes desirable to trigger a function call after a state is executed,
for this the :mod:`module.wait <salt.states.module.wait>` state can be used:

.. code-block:: yaml

    mine.send:
      module.wait:
        - name: network.interfaces
        - watch:
          - file: /etc/network/interfaces

All arguments that the ``module`` state does not consume are passed through to
the execution module function being executed:

.. code-block:: yaml

    fetch_out_of_band:
      module.run:
        - name: git.fetch
        - cwd: /path/to/my/repo
        - user: myuser
        - opts: '--all'

Due to how the state system works, if a module function accepts an
argument called, ``name``, then ``m_name`` must be used to specify that
argument, to avoid a collision with the ``name`` argument.

Here is a list of keywords hidden by the state system, which must be prefixed
with ``m_``:

* fun
* name
* names
* state
* saltenv

For example:

.. code-block:: yaml

    disable_nfs:
      module.run:
        - name: service.disable
        - m_name: nfs

Note that some modules read all or some of the arguments from a list of keyword
arguments. For example:

.. code-block:: yaml

    mine.send:
      module.run:
        - func: network.ip_addrs
        - kwargs:
            interface: eth0

.. code-block:: yaml

    cloud.create:
      module.run:
        - func: cloud.create
        - provider: test-provider
        - m_names:
          - test-vlad
        - kwargs: {
              ssh_username: 'ubuntu',
              image: 'ami-8d6d9daa',
              securitygroup: 'default',
              size: 'c3.large',
              location: 'ap-northeast-1',
              delvol_on_destroy: 'True'
          }

Another example that creates a recurring task that runs a batch file on a
Windows system:

.. code-block:: yaml

    eventsviewer:
      module.run:
        - name: task.create_task
        - m_name: 'events-viewer'
        - user_name: System
        - kwargs: {
              action_type: 'Execute',
              cmd: 'c:\netops\scripts\events_viewer.bat',
              trigger_type: 'Daily',
              start_date: '2017-1-20',
              start_time: '11:59PM'
        }

Another option is to use the `module.xrun`. With which you can call one (or more!)
functions at once the following way:

.. code-block:: yaml

    call_something:
      module.xrun:
        git.fetch:
          - cwd: /path/to/my/repo
          - user: myuser
          - opts: '--all'

Unlike `module.run`, the `module.xrun` does not have reserved words you should
specially prefix to distinguish them. No need to extra-pass `kwargs` either.
For example, this is the same example from `module.run`:

.. code-block:: yaml

    mine.send:
      module.xrun:
        network.ip_addrs:
          - interface: eth0

Or the examlpe above can be written as following:

.. code-block:: yaml

    eventsviewer:
      module.xrun:
        task.create_task:
          - name: events-viewer
          - user_name: System
          - action_type: Execute
          - cmd: 'c:\netops\scripts\events_viewer.bat'
          - trigger_type: 'Daily'
          - start_date: '2017-1-20'
          - start_time: '11:59PM'

'''
from __future__ import absolute_import

# Import salt libs
import salt.loader
import salt.utils
import salt.utils.jid
from salt.ext.six.moves import range
from salt.exceptions import SaltInvocationError


def wait(name, **kwargs):
    '''
    Run a single module function only if the watch statement calls it

    ``name``
        The module function to execute

    ``**kwargs``
        Pass any arguments needed to execute the function

    .. note::
        Like the :mod:`cmd.run <salt.states.cmd.run>` state, this state will
        return ``True`` but not actually execute, unless one of the following
        two things happens:

        1. The state has a :ref:`watch requisite <requisites-watch>`, and
           the state which it is watching changes.

        2. Another state has a :ref:`watch_in requisite
           <requisites-watch-in>` which references this state, and the state
           wth the ``watch_in`` changes.
    '''
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}

# Alias module.watch to module.wait
watch = salt.utils.alias_function(wait, 'watch')


def xrun(**kwargs):
    '''
    Run a single module function or a range of module functions in a batch.
    Supersedes `module.run` function, which requires `m_` prefix to function-specific parameters.

    :param returner:
        Specify a common returner for the whole batch to send the return data

    :param kwargs:
        Pass any arguments needed to execute the function(s)

    .. code-block:: yaml
      some_id_of_state:
        module.xrun:
          - network.ip_addrs:
            - interface: eth0
          - cloud.create:
            - names:
              - test-isbm-1
              - test-isbm-2
            - ssh_username: sles
            - image: sles12sp2
            - securitygroup: default
            - size: 'c3.large'
            - location: ap-northeast-1
            - delvol_on_destroy: True


    :return:
    '''

    if 'name' in kwargs:
        kwargs.pop('name')
    ret = {
        'name': kwargs.keys(),
        'changes': {},
        'comment': '',
        'result': None,
    }

    functions = [func for func in kwargs.keys() if '.' in func]
    for func in functions:
        if func not in __salt__:
            ret['comment'] = "Module function '{0}' is not available".format(func)
            ret['result'] = False
        elif __opts__['test']:
            ret['comment'] = "Module function '{0}' is set to execute".format(func)
            ret['result'] = True

    if ret['result'] is None:
        ret['result'] = True

        failures = []
        success = []
        for func in functions:
            try:
                func_ret = _call_function(func, returner=kwargs.get('returner'),
                                          func_args=kwargs.get(func))
                if not _get_result(func_ret, ret['changes'].get('ret', {})):
                    if isinstance(func_ret, dict):
                        failures.append("'{0}' failed: {1}".format(
                            func, func_ret.get('comment', '(error message N/A)')))
                else:
                    success.append('{0}: {1}'.format(
                        func, func_ret.get('comment', 'Success') if isinstance(func_ret, dict) else func_ret))
            except (SaltInvocationError, TypeError) as ex:
                failures.append("'{0}' failed: {1}".format(func, ex))
        ret['comment'] = ', '.join(failures + success)
        ret['result'] = not bool(failures)

    return ret


def _call_function(name, returner=None, **kwargs):
    '''
    Calls a function from the specified module.

    :param name:
    :param kwargs:
    :return:
    '''
    argspec = salt.utils.args.get_function_argspec(__salt__[name])
    func_kw = dict(zip(argspec.args[-len(argspec.defaults or []):], argspec.defaults or []))
    func_args = []
    for funcset in kwargs.get('func_args') or {}:
        if isinstance(funcset, dict):
            func_kw.update(funcset)
        else:
            func_args.append(funcset)

    missing = []
    for arg in argspec.args:
        if arg not in func_kw:
            missing.append(arg)
    if missing:
        raise SaltInvocationError('Missing arguments: {0}'.format(', '.join(missing)))

    mret = __salt__[name](*func_args, **func_kw)
    if returner is not None:
        returners = salt.loader.returners(__opts__, __salt__)
        if returner in returners:
            returners[returner]({'id': __opts__['id'], 'ret': mret,
                                 'fun': name, 'jid': salt.utils.jid.gen_jid()})

    return mret


def run(name, **kwargs):
    '''
    Run a single module function

    ``name``
        The module function to execute

    ``returner``
        Specify the returner to send the return of the module execution to

    ``kwargs``
        Pass any arguments needed to execute the function
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': None}
    if name not in __salt__:
        ret['comment'] = 'Module function {0} is not available'.format(name)
        ret['result'] = False
        return ret

    if __opts__['test']:
        ret['comment'] = 'Module function {0} is set to execute'.format(name)
        return ret

    aspec = salt.utils.args.get_function_argspec(__salt__[name])
    args = []
    defaults = {}

    arglen = 0
    deflen = 0
    if isinstance(aspec.args, list):
        arglen = len(aspec.args)
    if isinstance(aspec.defaults, tuple):
        deflen = len(aspec.defaults)
    # Match up the defaults with the respective args
    for ind in range(arglen - 1, -1, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            defaults[aspec.args[ind]] = aspec.defaults[-minus]
    # overwrite passed default kwargs
    for arg in defaults:
        if arg == 'name':
            if 'm_name' in kwargs:
                defaults[arg] = kwargs.pop('m_name')
        elif arg == 'fun':
            if 'm_fun' in kwargs:
                defaults[arg] = kwargs.pop('m_fun')
        elif arg == 'state':
            if 'm_state' in kwargs:
                defaults[arg] = kwargs.pop('m_state')
        elif arg == 'saltenv':
            if 'm_saltenv' in kwargs:
                defaults[arg] = kwargs.pop('m_saltenv')
        if arg in kwargs:
            defaults[arg] = kwargs.pop(arg)
    missing = set()
    for arg in aspec.args:
        if arg == 'name':
            rarg = 'm_name'
        elif arg == 'fun':
            rarg = 'm_fun'
        elif arg == 'names':
            rarg = 'm_names'
        elif arg == 'state':
            rarg = 'm_state'
        elif arg == 'saltenv':
            rarg = 'm_saltenv'
        else:
            rarg = arg
        if rarg not in kwargs and arg not in defaults:
            missing.add(rarg)
            continue
        if arg in defaults:
            args.append(defaults[arg])
        else:
            args.append(kwargs.pop(rarg))
    if missing:
        comment = 'The following arguments are missing:'
        for arg in missing:
            comment += ' {0}'.format(arg)
        ret['comment'] = comment
        ret['result'] = False
        return ret

    if aspec.varargs and aspec.varargs in kwargs:
        varargs = kwargs.pop(aspec.varargs)

        if not isinstance(varargs, list):
            msg = "'{0}' must be a list."
            ret['comment'] = msg.format(aspec.varargs)
            ret['result'] = False
            return ret

        args.extend(varargs)

    nkwargs = {}
    if aspec.keywords and aspec.keywords in kwargs:
        nkwargs = kwargs.pop(aspec.keywords)

        if not isinstance(nkwargs, dict):
            msg = "'{0}' must be a dict."
            ret['comment'] = msg.format(aspec.keywords)
            ret['result'] = False
            return ret

    try:
        if aspec.keywords:
            mret = __salt__[name](*args, **nkwargs)
        else:
            mret = __salt__[name](*args)
    except Exception as e:
        ret['comment'] = 'Module function {0} threw an exception. Exception: {1}'.format(name, e)
        ret['result'] = False
        return ret
    else:
        if mret is not None or mret is not {}:
            ret['changes']['ret'] = mret

    if 'returner' in kwargs:
        ret_ret = {
                'id': __opts__['id'],
                'ret': mret,
                'fun': name,
                'jid': salt.utils.jid.gen_jid()}
        returners = salt.loader.returners(__opts__, __salt__)
        if kwargs['returner'] in returners:
            returners[kwargs['returner']](ret_ret)
    ret['comment'] = 'Module function {0} executed'.format(name)
    ret['result'] = _get_result(mret, ret['changes'].get('ret', {}))

    return ret


def _get_result(func_ret, changes):
    res = True
    # if mret is a dict and there is retcode and its non-zero
    if isinstance(func_ret, dict) and func_ret.get('retcode', 0) != 0:
        res = False
        # if its a boolean, return that as the result
    elif isinstance(func_ret, bool):
        res = func_ret
    else:
        changes_ret = changes.get('ret', {})
        if isinstance(changes_ret, dict):
            if isinstance(changes_ret.get('result', {}), bool):
                res = changes_ret.get('result', {})
            elif changes_ret.get('retcode', 0) != 0:
                res = False

    return res

mod_watch = salt.utils.alias_function(run, 'mod_watch')
