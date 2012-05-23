import os


def shell():
    '''
    Return the default shell to use on this system
    '''
    # Provides:
    #   shell
    return {'shell': os.environ.get('SHELL', '/bin/sh')}
