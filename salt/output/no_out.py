'''
Display no output.
'''

def __virtual__():
    return 'none'

def output(ret):
    '''
    Don't display data. Used when you only are interested in the
    return.
    '''
    return ''
