import salt.utils.cache

'''
This is a module used in
unit.utils.cache to test
the context wrapper functions.
'''

def __virtual__():
    return True

@salt.utils.cache.context_cache
def test_context_module():
    if 'called' in __context__:
        __context__['called'] += 1
    else:
        __context__['called'] = 0
    return __context__
