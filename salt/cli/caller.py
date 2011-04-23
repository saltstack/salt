'''
The caller module is used as a frontend to manage direct calls to the salt
minion modules.
'''
# Import python modules
import os
import distutils.sysconfig
# Import salt libs
import salt.loader


class Caller(object):
    '''
    Object to wrap the calling of local salt modules for the salt-call command
    '''
    def __init__(self, opts):
        '''
        Pass in the command line options
        '''
        self.opts = opts
        module_dirs = [
            os.path.join(distutils.sysconfig.get_python_lib(), 'salt/modules'),
            ] + opts['module_dirs']
        self.loader = salt.loader.Loader(module_dirs)

    def call(self):
        '''
        Call the module
        '''
        return self.loader.call(self.opts['fun'], self.opts['arg'])

    def run(self):
        '''
        Execute the salt call logic
        '''
        print self.call()


