'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''
# Import python libs
import sys
import os
import copy
import multiprocessing

# Import saltcloud libs
import saltcloud.utils
import saltcloud.loader
import salt.client
import salt.utils

# Import third party libs
import yaml


class Cloud(object):
    '''
    An object for the creation of new vms
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
            return vm_['provider']
        if 'provider' in self.opts:
            if '{0}.create'.format(self.opts['provider']) in self.clouds:
                return self.opts['provider']

    def get_providers(self):
        '''
        Return the providers configured within the vm settings
        '''
        provs = set()
        for fun in self.clouds:
            if not '.' in fun:
                continue
            provs.add(fun[:fun.index('.')])
        return provs

    def map_providers(self, query='list_nodes'):
        '''
        Return a mapping of what named vms are running on what vm providers
        based on what providers are defined in the configs and vms
        '''
        provs = self.get_providers()
        pmap = {}
        for prov in provs:
            fun = '{0}.{1}'.format(prov, query)
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

    def image_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        provs = self.get_providers()
        images = {}
        for prov in provs:
            # If all providers are not desired, then don't get them
            if not lookup == 'all':
                if not lookup == prov:
                    continue
            fun = '{0}.avail_images'.format(prov)
            if not fun in self.clouds:
                # The capability to gather images is not supported by this
                # cloud module
                continue
            images[prov] = self.clouds[fun]()
        return images

    def size_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        provs = self.get_providers()
        sizes = {}
        for prov in provs:
            # If all providers are not desired, then don't get them
            if not lookup == 'all':
                if not lookup == prov:
                    continue
            fun = '{0}.avail_sizes'.format(prov)
            if not fun in self.clouds:
                # The capability to gather sizes is not supported by this
                # cloud module
                continue
            sizes[prov] = self.clouds[fun]()
        return sizes

    def create_all(self):
        '''
        Create/Verify the vms in the vm data
        '''
        for vm_ in self.opts['vm']:
            self.create(vm_)

    def destroy(self, names):
        '''
        Destroy the named vms
        '''
        pmap = self.map_providers()
        dels = {}
        for prov, nodes in pmap.items():
            dels[prov] = []
            for node in nodes:
                if node in names:
                    dels[prov].append(node)
        for prov, names_ in dels.items():
            fun = '{0}.destroy'.format(prov)
            for name in names_:
                if self.clouds[fun](name):
                    saltcloud.utils.remove_key(self.opts['pki_dir'], name)

    def create(self, vm_):
        '''
        Create a single vm
        '''
        fun = '{0}.create'.format(self.provider(vm_))
        if not fun in self.clouds:
            print('Public cloud provider {0} is not available'.format(
                self.provider(vm_))
                )
            return
        priv, pub = saltcloud.utils.gen_keys(
                saltcloud.utils.get_option('keysize', self.opts, vm_)
                )
        vm_['pub_key'] = pub
        vm_['priv_key'] = priv
        ok = False

        if 'script' in vm_:
            vm_['os'] = vm_['script']

        try:
            ok = self.clouds['{0}.create'.format(self.provider(vm_))](vm_)
        except KeyError as exc:
            print('Failed to create vm {0}. Configuration value {1} needs '
                  'to be set'.format(vm_['name'], exc))
        if ok != False:
            saltcloud.utils.accept_key(self.opts['pki_dir'], pub, vm_['name'])

    def profile_provider(self, profile=None):
        for definition in self.opts['vm']:
            if definition['profile'] == profile:
                return definition['provider']

    def run_profile(self):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        pmap = self.map_providers()
        found = False
        for name in self.opts['names']:
            for vm_ in self.opts['vm']:
                if vm_['profile'] == self.opts['profile']:
                    # It all checks out, make the vm
                    found = True
                    if name in pmap.get(self.provider(vm_), []):
                        # The specified vm already exists, don't make it anew
                        print("{0} already exists on {1}".format(name, self.provider(vm_)))
                        continue
                    vm_['name'] = name
                    if self.opts['parallel']:
                        multiprocessing.Process(
                                target=lambda: self.create(vm_),
                                ).start()
                    else:
                        self.create(vm_)
        if not found:
            print('Profile {0} is not defined'.format(self.opts['profile']))


class Map(Cloud):
    '''
    Create a vm stateful map execution object
    '''
    def __init__(self, opts):
        Cloud.__init__(self, opts)
        self.map = self.read()

    def interpolated_map(self, query=None):
        query_map = self.map_providers(query=query)
        full_map = {}
        dmap = self.read()
        for profile, vmap in dmap.items():
            provider = self.profile_provider(profile)
            vms = [i.keys() for i in vmap]
            for vm in vms:
                if provider not in full_map:
                    full_map[provider] = {}
    
                if vm[0] in query_map[provider]:
                    full_map[provider][vm[0]] = query_map[provider][vm[0]]
                else:
                    full_map[provider][vm[0]] = 'Absent'
        return full_map

    def delete_map(self, query=None):
        query_map = self.interpolated_map(query=query)
        names = []
        for profile in query_map:
            for vm in query_map[profile]:
                names.append(vm)
        return names

    def read(self):
        '''
        Read in the specified map file and return the map structure
        '''
        if not self.opts['map']:
            return {}
        if not os.path.isfile(self.opts['map']):
            sys.stderr.write('The specified map file does not exist: {0}\n'.format(self.opts['map']))
            sys.exit(1)
        try:
            with open(self.opts['map'], 'rb') as fp_:
                map_ = yaml.load(fp_.read())
        except Exception:
            return {}
        if 'include' in map_:
            map_ = salt.config.include_config(map_, self.opts['map'])
        return map_

    def map_data(self):
        '''
        Create a data map of what to execute on
        '''
        ret = {}
        pmap = self.map_providers()
        ret['create'] = {}
        exist = set()
        defined = set()
        for profile in self.map:
            pdata = {}
            for pdef in self.opts['vm']:
                # The named profile does not exist
                if pdef.get('profile', '') == profile:
                    pdata = pdef
            if not pdata:
                continue
            for name in self.map[profile]:
                nodename = name
                if isinstance(name, dict):
                    nodename = (name.keys()[0])
                defined.add(nodename)
                ret['create'][nodename] = pdata
        for prov in pmap:
            for name in pmap[prov]:
                exist.add(name)
                if name in ret['create']:
                    if prov != 'aws' or pmap['aws'][name]['state'] != 2:
                      ret['create'].pop(name)
        if self.opts['hard']:
            # Look for the items to delete
            ret['destroy'] = exist.difference(defined)
        return ret

    def run_map(self):
        '''
        Execute the contents of the vm map
        '''
        dmap = self.map_data()
        msg = 'The following virtual machines are set to be created:\n'
        for name in dmap['create']:
            msg += '  {0}\n'.format(name)
        if 'destroy' in dmap:
            msg += 'The following virtual machines are set to be destroyed:\n'
            for name in dmap['destroy']:
                msg += '  {0}\n'.format(name)
        print(msg)
        res = raw_input('Proceed? [N/y]')
        if not res.lower().startswith('y'):
            return
        # We are good to go, execute!
        # Generate the fingerprint of the master pubkey in
        #     order to mitigate man-in-the-middle attacks
        master_pub = self.opts['pki_dir'] + '/master.pub'
        master_finger = ''
        if os.path.isfile(master_pub) and hasattr(salt.utils, 'pem_finger'):
            master_finger = salt.utils.pem_finger(master_pub)
        for name, profile in dmap['create'].items():
            tvm = copy.deepcopy(profile)
            tvm['name'] = name
            tvm['master_finger'] = master_finger
            for miniondict in self.map[tvm['profile']]:
                if isinstance(miniondict, dict):
                    if name in miniondict:
                        if 'grains' in miniondict[name]:
                            tvm['map_grains'] = miniondict[name]['grains']
                        if 'minion' in miniondict[name]:
                            tvm['map_minion'] = miniondict[name]['minion']
            if self.opts['parallel']:
                multiprocessing.Process(
                        target=lambda: self.create(tvm)
                        ).start()
            else:
                self.create(tvm)
        for name in dmap.get('destroy', set()):
            self.destroy(name)
