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

    def run_data(self):
        '''
        Create/Verify the vms in the vm data
        '''
        for vm_ in self.opts['vm']:
            self.create(vm_)
