'''
Used to manage the thorium register. The thorium register is where compound
values are stored and computed, such as averages etc.
'''

# import python libs
import fnmatch

__func_alias__ = {
    'set_': 'set',
}

def set_(name, add, match):
    '''
    Add a value to the named set
    '''
    ret = {'name': name,
           'changes': {},
           'comment': '',
           'result': True}
    if name not in __reg__:
        __reg__[name] = set()
    for event in __events__:
        if fnmatch.fnmatch(event['tag'], match):
            val = event['data'].get(add)
            if val is None:
                val = 'None'
            ret['changes'][add] = val
            __reg__[name].add(val)
    return ret
