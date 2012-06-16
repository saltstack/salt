'''
Execution of Salt modules from within states.
=============================================

Individual module calls can be made via states. to call a single module
function use the run function.

One issue exists, since the name argument is present in the state call and is
present in many modules, this argument will need to be replaced in the sls
data with the argument m_name.
'''

# Import salt libs
import salt.state


def wait(name, **kwargs):
    '''
    Run a single module function only if the watch statement calls it

    name
        The module function to execute

    **kwargs
        Pass any arguments needed to execute the function
    '''
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': ''}


def run(name, **kwargs):
    '''
    Run a single module function

    name
        The module function to execute

    **kwargs
        Pass any arguments needed to execute the function
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': None}
    if not name in __salt__:
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
    for ind in range(arglen - 1, 0, -1):
        minus = arglen - ind
        if deflen - minus > -1:
            defaults[aspec[0][ind]] = aspec[3][-minus]
    # overwrite passed default kwargs
    for arg in defaults:
        if arg == 'name':
            if 'm_name' in kwargs:
                defaults[arg] = kwargs.pop('m_name')
        if arg in kwargs:
            defaults[arg] = kwargs.pop(arg)
    missing = set()
    for arg in aspec[0]:
        if arg == 'name':
            rarg = 'm_name'
        else:
            rarg = arg
        if rarg not in kwargs and rarg not in defaults:
            missing.add(rarg)
            continue
        if rarg in defaults:
            args.append(defaults[rarg])
        else:
            args.append(kwargs.pop(rarg))
    if missing:
        comment = 'The following arguments are missing:'
        for arg in missing:
            comment += ' {0}'.format(arg)
        ret['comment'] = comment
        ret['result'] = False
        return ret

    try:
        if aspec[2]:
            mret = __salt__[name](*args, **kwargs)
        else:
            mret = __salt__[name](*args)
    except Exception:
        ret['comment'] = 'Module function {0} threw an exception'.format(name)
        ret['result'] = False

    ret['comment'] = 'Module function {0} executed'.format(name)
    ret['result'] = True
    ret['changes']['ret'] = mret
    return ret

mod_watch = run
