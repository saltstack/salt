'''
Render is a module used to parse the render files into high salt state data
structures.

The render system uses render modules which are plugable interfaces under the
render directory.
'''
# Import salt modules
import salt.loader

class Render(object):
    '''
    Render state files.
    '''
    def __init__(self, opts):
        pass
