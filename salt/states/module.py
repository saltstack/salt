# -*- coding: utf-8 -*-
r'''
Execution of Salt modules from within states
============================================

.. note::

    There are two styles of calling ``module.run``. **The legacy style will no
    longer be available starting in the Sodium release.** To opt-in early to the
    new style you must add the following to your ``/etc/salt/minion`` config
    file:

    .. code-block:: yaml

        use_superseded:
          - module.run

With `module.run` these states allow individual execution module calls to be
made via states. Here's a contrived example, to show you how it's done:

.. code-block:: yaml

    # New Style
    test.random_hash:
      module.run:
        - test.random_hash:
          - size: 42
          - hash_type: sha256

    # Legacy Style
    test.random_hash:
      module.run:
        - size: 42
        - hash_type: sha256

In the new style, the state ID (``test.random_hash``, in this case) is
irrelevant when using ``module.run``. It could have very well been written:

.. code-block:: yaml

    Generate a random hash:
      module.run:
        - test.random_hash:
          - size: 42
          - hash_type: sha256

For a simple state like that it's not a big deal, but if the module you're
using has certain parameters, things can get cluttered, fast. Using the
contrived custom module (stuck in ``/srv/salt/_modules/foo.py``, or your
configured file_roots_):

.. code-block:: python

    def bar(name, names, fun, state, saltenv):
        return "Name: {name} Names: {names} Fun: {fun} State: {state} Saltenv: {saltenv}".format(**locals())

Your legacy state has to look like this:

.. code-block:: yaml

    # Legacy style
    Unfortunate example:
      module.run:
      - name: foo.bar
      - m_name: Some name
      - m_names:
        - Such names
        - very wow
      - m_state: Arkansas
      - m_fun: Such fun
      - m_saltenv: Salty

With the new style it's much cleaner:

.. code-block:: yaml

    # New style
    Better:
      module.run:
      - foo.bar:
        - name: Some name
        - names:
          - Such names
          - very wow
        - state: Arkansas
        - fun: Such fun
        - saltenv: Salty

The new style also allows multiple modules in one state. For instance, you can
do this:

.. code-block:: yaml

    Do many things:
      module.run:
        - test.random_hash:
          - size: 10
          - hash_type: md5
        # Note the `:` at the end
        - test.true:
        - test.arg:
          - this
          - has
          - args
          - and: kwargs
          - isn't: that neat?
        # Note the `:` at the end, too
        - test.version:
        - test.fib:
          - 4

Where in the legacy style you would have had to split your states like this:

.. code-block:: yaml

    test.random_hash:
      module.run:
        - size: 10
        - hash_type: md5

    test.nop:
      module.run

    test.arg:
      module.run:
        - args:
          - this
          - has
          - args
        - kwargs:
            and: kwargs
            isn't: that neat?

    test.version:
      module.run

Another difference is that in the legacy style, unconsumed arguments to the
``module`` state were simply passed into the module function being executed:

.. code-block:: yaml

    show off module.run with args:
      module.run:
        - name: test.random_hash
        - size: 42
        - hash_type: sha256

The new style is much more explicit, with the arguments and keyword arguments
being nested under the name of the function:

.. code-block:: yaml

    show off module.run with args:
      module.run:
        # Note the lack of `name: `, and trailing `:`
        - test.random_hash:
          - size: 42
          - hash_type: sha256

If the function takes ``*args``, they can be passed in as well:

.. code-block:: yaml

    args and kwargs:
      module.run:
        - test.arg:
          - isn't
          - this
          - fun
          - this: that
          - salt: stack

Modern Examples
---------------

Here are some other examples using the modern ``module.run``:

.. code-block:: yaml

    fetch_out_of_band:
      module.run:
        - git.fetch:
          - cwd: /path/to/my/repo
          - user: myuser
          - opts: '--all'

A more complex example:

.. code-block:: yaml

    eventsviewer:
      module.run:
        - task.create_task:
          - name: events-viewer
          - user_name: System
          - action_type: Execute
          - cmd: 'c:\netops\scripts\events_viewer.bat'
          - trigger_type: 'Daily'
          - start_date: '2017-1-20'
          - start_time: '11:59PM'

It is sometimes desirable to trigger a function call after a state is executed,
for this the :mod:`module.wait <salt.states.module.wait>` state can be used:

.. code-block:: yaml

    add example to hosts:
      file.append:
        - name: /etc/hosts
        - text: 203.0.113.13     example.com

    # New Style
    mine.send:
      module.wait:
        # Again, note the trailing `:`
        - hosts.list_hosts:
        - watch:
          - file: add example to hosts

Legacy (Default) Examples
-------------------------

If you're using the legacy ``module.run``, due to how the state system works,
if a module function accepts an argument called, ``name``, then ``m_name`` must
be used to specify that argument, to avoid a collision with the ``name``
argument.

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

Other modules take the keyword arguments using this style:

.. code-block:: yaml

     mac_enable_ssh:
       module.run:
         - name: system.set_remote_login
         - enable: True

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

.. _file_roots: https://docs.saltstack.com/en/latest/ref/configuration/master.html#file-roots
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import salt libs
import salt.loader
import salt.utils.args
import salt.utils.functools
import salt.utils.jid
from salt.ext import six
from salt.ext.six.moves import range
from salt.ext.six.moves import zip
from salt.exceptions import SaltInvocationError
from salt.utils.decorators import with_deprecated


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
watch = salt.utils.functools.alias_function(wait, 'watch')


@with_deprecated(globals(), "Sodium", policy=with_deprecated.OPT_IN)
def run(**kwargs):
    '''
    Run a single module function or a range of module functions in a batch.
    Supersedes ``module.run`` function, which requires ``m_`` prefix to
    function-specific parameters.

    :param returner:
        Specify a common returner for the whole batch to send the return data

    :param kwargs:
        Pass any arguments needed to execute the function(s)

    .. code-block:: yaml

      some_id_of_state:
        module.run:
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
        'name': list(kwargs),
        'changes': {},
        'comment': '',
        'result': None,
    }

    functions = [func for func in kwargs.keys() if '.' in func]
    missing = []
    tests = []
    for func in functions:
        func = func.split(':')[0]
        if func not in __salt__:
            missing.append(func)
        elif __opts__['test']:
            tests.append(func)

    if tests or missing:
        ret['comment'] = ' '.join([
            missing and "Unavailable function{plr}: "
                        "{func}.".format(plr=(len(missing) > 1 or ''),
                                         func=(', '.join(missing) or '')) or '',
            tests and "Function{plr} {func} to be "
                      "executed.".format(plr=(len(tests) > 1 or ''),
                                         func=(', '.join(tests)) or '') or '',
        ]).strip()
        ret['result'] = not (missing or not tests)

    if ret['result'] is None:
        ret['result'] = True

        failures = []
        success = []
        for func in functions:
            _func = func.split(':')[0]
            try:
                func_ret = _call_function(_func, returner=kwargs.get('returner'),
                                          func_args=kwargs.get(func))
                if not _get_result(func_ret, ret['changes'].get('ret', {})):
                    if isinstance(func_ret, dict):
                        failures.append("'{0}' failed: {1}".format(
                            func, func_ret.get('comment', '(error message N/A)')))
                else:
                    success.append('{0}: {1}'.format(
                        func, func_ret.get('comment', 'Success') if isinstance(func_ret, dict) else func_ret))
                    ret['changes'][func] = func_ret
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

    # func_kw is initialized to a dictionary of keyword arguments the function to be run accepts
    func_kw = dict(zip(argspec.args[-len(argspec.defaults or []):],  # pylint: disable=incompatible-py3-code
                   argspec.defaults or []))

    # func_args is initialized to a list of positional arguments that the function to be run accepts
    func_args = argspec.args[:len(argspec.args or []) - len(argspec.defaults or [])]
    arg_type, na_type, kw_type = [], {}, False
    for funcset in reversed(kwargs.get('func_args') or []):
        if not isinstance(funcset, dict):
            # We are just receiving a list of args to the function to be run, so just append
            # those to the arg list that we will pass to the func.
            arg_type.append(funcset)
        else:
            for kwarg_key in six.iterkeys(funcset):
                # We are going to pass in a keyword argument. The trick here is to make certain
                # that if we find that in the *args* list that we pass it there and not as a kwarg
                if kwarg_key in func_args:
                    arg_type.append(funcset[kwarg_key])
                    continue
                else:
                    # Otherwise, we're good and just go ahead and pass the keyword/value pair into
                    # the kwargs list to be run.
                    func_kw.update(funcset)
    arg_type.reverse()
    _exp_prm = len(argspec.args or []) - len(argspec.defaults or [])
    _passed_prm = len(arg_type)
    missing = []
    if na_type and _exp_prm > _passed_prm:
        for arg in argspec.args:
            if arg not in func_kw:
                missing.append(arg)
    if missing:
        raise SaltInvocationError('Missing arguments: {0}'.format(', '.join(missing)))
    elif _exp_prm > _passed_prm:
        raise SaltInvocationError('Function expects {0} parameters, got only {1}'.format(
            _exp_prm, _passed_prm))

    mret = __salt__[name](*arg_type, **func_kw)
    if returner is not None:
        returners = salt.loader.returners(__opts__, __salt__)
        if returner in returners:
            returners[returner]({'id': __opts__['id'], 'ret': mret,
                                 'fun': name, 'jid': salt.utils.jid.gen_jid(__opts__)})

    return mret


def _run(name, **kwargs):
    '''
    .. deprecated:: 2017.7.0
       Function name stays the same, behaviour will change.

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

    if aspec.varargs:
        if aspec.varargs == 'name':
            rarg = 'm_name'
        elif aspec.varargs == 'fun':
            rarg = 'm_fun'
        elif aspec.varargs == 'names':
            rarg = 'm_names'
        elif aspec.varargs == 'state':
            rarg = 'm_state'
        elif aspec.varargs == 'saltenv':
            rarg = 'm_saltenv'
        else:
            rarg = aspec.varargs

        if rarg in kwargs:
            varargs = kwargs.pop(rarg)

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
                'jid': salt.utils.jid.gen_jid(__opts__)}
        returners = salt.loader.returners(__opts__, __salt__)
        if kwargs['returner'] in returners:
            returners[kwargs['returner']](ret_ret)
    ret['comment'] = 'Module function {0} executed'.format(name)
    ret['result'] = _get_result(mret, ret['changes'])

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
            # Explore dict in depth to determine if there is a
            # 'result' key set to False which sets the global
            # state result.
            else:
                res = _get_dict_result(changes_ret)

    return res


def _get_dict_result(node):
    ret = True
    for key, val in six.iteritems(node):
        if key == 'result' and val is False:
            ret = False
            break
        elif isinstance(val, dict):
            ret = _get_dict_result(val)
            if ret is False:
                break
    return ret


mod_watch = salt.utils.functools.alias_function(run, 'mod_watch')
