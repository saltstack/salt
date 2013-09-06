'''
Directly manage the salt fileserver plugins
'''

# Import salt libs
import salt.fileserver


def update():
    '''
    Execute an update for all of the configured fileserver backends
    '''
    fileserver = salt.fileserver.Fileserver(__opts__)
    fileserver.update()
