'''
The matcher subsystem needs a function called 'confirm_top', which
takes the data passed to a top file environment and determines if that
data matches this minion.
'''

def confirm_top(self, match, data, nodegroups=None):
    '''
    Takes the data passed to a top file environment and determines if the
    data matches this minion
    '''
    matcher = 'compound'
    if not data:
        log.error('Received bad data when setting the match from the top '
                  'file')
        return False
    for item in data:
        if isinstance(item, dict):
            if 'match' in item:
                matcher = item['match']
    if hasattr(self, matcher + '_match'):
        funcname = '{0}_match'.format(matcher)
        if matcher == 'nodegroup':
            return getattr(self, funcname)(match, nodegroups)
        return getattr(self, funcname)(match)
    else:
        log.error('Attempting to match with unknown matcher: %s', matcher)
