import os

def shell():
    '''
    Return the default shell to use on this system
    '''
    # Provides:
    #   shell
    ret = {'shell': '/bin/sh'}
    if 'SHELL' in os.environ:
        ret['shell'] = os.environ['SHELL']
    return ret

