import salt.utils.decorators
import time

def _fallbackfunc():
    return False, 'fallback'


def working_function():
    '''
    CLI Example::
    '''
    return True

@salt.utils.decorators.depends('time')
def depends():
    ret = {'ret': True,
           'time': time.time()}
    return ret

@salt.utils.decorators.depends('time123')
def missing_depends():
    return True

@salt.utils.decorators.depends('time', fallback_funcion=_fallbackfunc)
def depends_will_fallback():
    ret = {'ret': True,
           'time': time.time()}
    return ret

@salt.utils.decorators.depends('time123', fallback_funcion=_fallbackfunc)
def missing_depends_will_fallback():
    ret = {'ret': True,
           'time': time.time()}
    return ret
