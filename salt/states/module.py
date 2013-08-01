'''
Execution of Salt modules from within states.
=============================================

Individual module calls can be made via states. to call a single module
function use the run function.

One issue exists, since the name and fun arguments are present in the state
call data structure and is present in many modules, this argument will need
to be replaced in the sls data with the arguments m_name and m_fun.
'''
# Import python libs
import datetime

# Import salt libs
import salt.state
import salt.loader


def wait(name, **kwargs):
    '''
    Run a single module function only if the watch statement calls it

    ``name``
        The module function to execute

    ``**kwargs``
        Pass any arguments needed to execute the function

    Note that this function actually does nothing -- however, if the `watch`
    is satisfied, then `mod_watch` (defined at the bottom of this file) will be
    run.  In this case, `mod_watch` is an alias for `run()`.
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

    aspec = salt.state._getargs(__salt__[name])

    args = []
    defaults = {}

    arglen = 0
    deflen = 0
    if isinstance(aspec[0], list):
        arglen = len(aspec[0])
    if isinstance(aspec[3], tuple):
        deflen = len(aspec[3])
    if aspec[2]:
        # This state accepts kwargs
        for key in kwargs:
            # Passing kwargs the conflict with args == stack trace
            if key in aspec[0]:
                continue
            defaults[key] = kwargs[key]
    # Match up the defaults with the respective args
    for ind in range(arglen - 1, -1, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            defaults[aspec[0][ind]] = aspec[3][-minus]
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
    for arg in aspec[0]:
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

    if aspec[1] and aspec[1] in kwargs:
        varargs = kwargs.pop(aspec[1])

        if not isinstance(varargs, list):
            msg = "'{0}' must be a list."
            ret['comment'] = msg.format(aspec[1])
            ret['result'] = False
            return ret

        args.extend(varargs)

    try:
        if aspec[2]:
            mret = __salt__[name](*args, **kwargs)
        else:
            mret = __salt__[name](*args)
    except Exception:
        ret['comment'] = 'Module function {0} threw an exception'.format(name)
        ret['result'] = False
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
