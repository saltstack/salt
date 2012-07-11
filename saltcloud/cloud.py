'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''
# Import python libs
import os
import copy
import multiprocessing

# Import saltcloud libs
import saltcloud.utils
import saltcloud.loader
import salt.client

# Import third party libs
import yaml


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

    def map_providers(self):
        '''
        Return a mapping of what named vms are running on what vm providers
        based on what providers are defined in the configs and vms
        '''
        provs = set()
        pmap = {}
        for vm_ in self.opts['vm']:
            provs.add(self.provider(vm_))
        for prov in provs:
            fun = '{0}.list_nodes'.format(prov)
            if not fun in self.clouds:
                print('Public cloud provider {0} is not available'.format(
                    self.provider(vm_))
                    )
                continue
            try:
                pmap[prov] = self.clouds[fun]()
            except Exception:
                # Failed to communicate with the provider, don't list any
                # nodes
                pmap[prov] = []
        return pmap

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
        try:
            self.clouds['{0}.create'.format(self.provider(vm_))](vm_)
        except KeyError as exc:
            print('Failed to create vm {0}. Configuration value {1} needs '
                  'to be set'.format(vm_['name'], exc))

    def run_profile(self):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        pmap = self.map_providers()
        for name in self.opts['names']:
            for vm_ in self.opts['vm']:
                if vm_['profile'] == self.opts['profile']:
                    # It all checks out, make the vm
                    if name in pmap[self.provider(vm_)]:
                        # The specified vm already exists, don't make it anew
                        continue
                    vm_['name'] = name
                    if self.opts['parallel']:
                        multiprocessing.Process(
                                target=lambda: self.create(vm_),
                                ).start()
                    else:
                        self.create(vm_)


class Map(Cloud):
    '''
    Create a vm stateful map execution object
    '''
    def __init__(self, opts):
        Cloud.__init__(self, opts)
        self.map = self.read()

    def read(self):
        '''
        Read in the specified map file and return the map structure
        '''
        if not self.opts['map']:
            return {}
        if not os.path.isfile(self.opts['map']):
            return {}
        try:
            with open(self.opts['map'], 'rb') as fp_:
                map_ = yaml.load(fp_.read())
        except Exception:
            return {}
        if 'include' in map_:
            map_ = salt.config.include_config(map_, self.opts['map'])
        return map_

    def run_map(self):
        '''
        Execute the contents of the vm map
        '''
        for profile in self.map:
            for name in self.map[profile]:
                for vm_ in self.opts['vm']:
                    if vm_['profile'] == profile:
                        tvm = copy.deepcopy(vm_)
                        tvm['name'] = name
                        if self.opts['parallel']:
                            multiprocessing.Process(
                                    target=lambda: self.create(tvm)
                                    ).start()
                        else:
                            self.create(tvm)
