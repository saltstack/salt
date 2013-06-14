import salt.utils.decorators
import time

def _fallbackfunc():
    return False, 'fallback'


def working_function():
    return True

@salt.utils.decorators.depends('time')
def depends():
    return True, time.time()

@salt.utils.decorators.depends('time123')
def missing_depends():
    return True, time.time()

@salt.utils.decorators.depends('time', fallback_funcion=_fallbackfunc)
def depends_will_fallback():
    return True, time.time()

@salt.utils.decorators.depends('time123', fallback_funcion=_fallbackfunc)
def missing_depends_will_fallback():
    return True, time.time()
