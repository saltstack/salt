# -*- coding: utf-8 -*-
'''
Execution of Salt modules from within states
============================================

These states allow individual execution module calls to be made via states. To
call a single module function use a :mod:`module.run <salt.states.module.run>`
state:

.. code-block:: yaml

    mine.send:
      module.run:
        - name: network.interfaces

Note that this example is probably unnecessary to use in practice, since the
``mine_functions`` and ``mine_interval`` config parameters can be used to
schedule updates for the mine (see :doc:`here </topics/mine/index>` for more
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

'''
from __future__ import absolute_import

# Import salt libs
import salt.loader
import salt.utils
import salt.utils.jid
from salt.ext.six.moves import range


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

        1. The state has a :doc:`watch requisite </ref/states/requisites>`, and
           the state which it is watching changes.

        2. Another state has a :doc:`watch_in requisite
           </ref/states/requisites>` which references this state, and the state
           wth the ``watch_in`` changes.
    '''
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}

# Alias module.watch to module.wait
watch = wait


def run(name, **kwargs):
    '''
    Run a single module function

    ``name``
        The module function to execute

    ``returner``
        Specify the returner to send the return of the module execution to

    ``**kwargs``
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

    ret['result'] = True
    # if mret is a dict and there is retcode and its non-zero
    if isinstance(mret, dict) and mret.get('retcode', 0) != 0:
        ret['result'] = False
    # if its a boolean, return that as the result
    elif isinstance(mret, bool):
        ret['result'] = mret
    else:
        changes_ret = ret['changes'].get('ret', {})
        if isinstance(changes_ret, dict) and changes_ret.get('retcode', 0) != 0:
            ret['result'] = False
    return ret

mod_watch = run  # pylint: disable=C0103
