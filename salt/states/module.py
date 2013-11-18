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
        - func: network.interfaces

Note that this example is probably unnecessary to use in practice, since the
``mine_functions`` and ``mine_interval`` config parameters can be used to
schedule updates for the mine (see :doc:`here </topics/mine/index>` for more
info).

It is sometimes desirable to trigger a function call after a state is executed,
for this the :mod:`module.wait <salt.states.module.wait>` state can be used:

.. code-block:: yaml

    mine.send:
      module.wait:
        - func: network.interfaces
        - watch:
          - file: /etc/network/interfaces

All arguments are passed through to the module function being executed.
However, due to how the state system works, if a module function accepts an
argument called, ``name``, then ``m_name`` must be used to specify that
argument, to avoid a collision with the ``name`` argument. For example:

.. code-block:: yaml

    disable_nfs:
      module.run:
        - name: service.disable
        - m_name: nfs
'''
# Import python libs
import datetime

# Import salt libs
import salt.loader
import salt.utils


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

    aspec = salt.utils.get_function_argspec(__salt__[name])

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
        if arg in kwargs:
            defaults[arg] = kwargs.pop(arg)
    missing = set()
    for arg in aspec.args:
        if arg == 'name':
            rarg = 'm_name'
        elif arg == 'fun':
            rarg = 'm_fun'
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
    except Exception:
        ret['comment'] = 'Module function {0} threw an exception'.format(name)
        ret['result'] = False
        return ret
    else:
        if mret:
            ret['changes']['ret'] = mret

    if 'returner' in kwargs:
        ret_ret = {
                'id': __opts__['id'],
                'ret': mret,
                'fun': name,
                'jid': '{0:%Y%m%d%H%M%S%f}'.format(datetime.datetime.now())}
        returners = salt.loader.returners(__opts__, __salt__)
        if kwargs['returner'] in returners:
            returners[kwargs['returner']](ret_ret)
    ret['comment'] = 'Module function {0} executed'.format(name)
    ret['result'] = True
    if ret['changes'].get('retcode', 0) != 0:
        ret['result'] = False
    return ret

mod_watch = run  # pylint: disable=C0103
