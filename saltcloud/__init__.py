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
            self.create(vm_)

    def create(self, vm_):
        '''
        Create a single vm
        '''
        fun = '{0}.create'.format(self.provider(vm_))
        if not fun in self.clouds:
            print('Public cloud provider {0} is not available'.format(
                self.provider(vm_))
                )
        priv, pub = saltcloud.utils.gen_keys(
                saltcloud.utils.get_option('keysize', self.opts, vm_)
                )
        saltcloud.utils.accept_key(self.opts['pki_dir'], pub, vm_['name'])
        vm_['pub_key'] = pub
        vm_['priv_key'] = priv
        self.clouds['{0}.create'.format(self.provider(vm_))](vm_)

    def run(self):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        if self.opts['names'] and self.opts['profile']:
            for name in self.opts['names']:
                for vm_ in self.opts['vm']:
                    if vm_['profile'] == self.opts['profile']:
                        vm_['name'] = name
                        self.create(name, vm_)
        else:
            self.create_all()
