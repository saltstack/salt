'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''

# Import saltcloud libs
import saltcloud.utils
import saltcloud.loader


class Cloud(object):
    '''
    An object for the creation of new inages
    '''
    def __init__(self, opts):
        self.opts = opts
        self.clouds = saltcloud.loader.clouds(self.opts)

    def provider(self, vm_):
        '''
        Return the top level module that will be used for the given vm data
        set
        '''
        if 'provider' in vm_:
            if '{0}.create'.format(vm_['provider']) in self.clouds:
                return vm_['provider']
        if 'provider' in self.opts:
            if '{0}.create'.format(self.opts['provider']) in self.clouds:
                return self.opts['provider']

    def create_all(self):
        '''
        Create/Verify the vms in the vm data
        '''
        for vm_ in self.opts['vm']:
            self.clouds['{0}.create'.format(self.provider(vm_))](vm_)
