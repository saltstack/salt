'''
Allow for flow based timers. These timers allow for a sleep to exist across
multiple runs of the flow
'''

def hold(name):
    '''
    Wait for a given period of time, then fire a result of True, requireing
    this state allows for an action to be blocked for evaluation based on
    time
    '''
    ret = {'name': name,
           'result': False,
           'comment': '',
           'changes': {}}
    start = time.time()
    if 'hold' not in __context__:
        __context__['hold'] = start
    if (start - __context__['hold']) > name:
        ret['result'] = True
        __context__['hold'] = start
    return ret
