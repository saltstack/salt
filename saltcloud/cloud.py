'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''
# Import python libs
import os
import sys
import copy
import multiprocessing
import logging

# Import saltcloud libs
import saltcloud.utils
import saltcloud.loader
import salt.client
import salt.utils

# Import third party libs
import yaml

# Get logging started
log = logging.getLogger(__name__)

try:
    from mako.template import Template
except:
    log.debug('Mako not available')


class Cloud(object):
    '''
    An object for the creation of new VMs
    '''
    def __init__(self, opts):
        self.opts = opts
        self.clouds = saltcloud.loader.clouds(self.opts)

    def provider(self, vm_):
        '''
        Return the top level module that will be used for the given VM data
        set
        '''
        if 'provider' in vm_:
            return vm_['provider']
        if 'provider' in self.opts:
            if '{0}.create'.format(self.opts['provider']) in self.clouds:
                return self.opts['provider']

    def get_providers(self):
        '''
        Return the providers configured within the VM settings
        '''
        provs = set()
        for fun in self.clouds:
            if not '.' in fun:
                continue
            provs.add(fun[:fun.index('.')])
        return provs

    def map_providers(self, query='list_nodes'):
        '''
        Return a mapping of what named VMs are running on what VM providers
        based on what providers are defined in the configs and VMs
        '''
        provs = self.get_providers()
        pmap = {}
        for prov in provs:
            fun = '{0}.{1}'.format(prov, query)
            if not fun in self.clouds:
                log.error(
                    'Public cloud provider {0} is not available'.format(
                        prov
                    )
                )
                continue
            try:
                pmap[prov] = self.clouds[fun]()
            except Exception:
                # Failed to communicate with the provider, don't list any
                # nodes
                pmap[prov] = []
        return pmap

    def location_list(self, lookup='all'):
        '''
        Return a mapping of all location data for available providers
        '''
        provs = self.get_providers()
        locations = {}
        for prov in provs:
            # If all providers are not desired, then don't get them
            if not lookup == 'all':
                if not lookup == prov:
                    continue
            fun = '{0}.avail_locations'.format(prov)
            if not fun in self.clouds:
                # The capability to gather locations is not supported by this
                # cloud module
                continue
            locations[prov] = self.clouds[fun]()
        return locations

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
        Create/Verify the VMs in the VM data
        '''
        for vm_ in self.opts['vm']:
            self.create(vm_)

    def destroy(self, names):
        '''
        Destroy the named VMs
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

    def reboot(self, names):
        '''
        Reboot the named VMs
        '''
        pmap = self.map_providers()
        acts = {}
        for prov, nodes in pmap.items():
            acts[prov] = []
            for node in nodes:
                if node in names:
                    acts[prov].append(node)
        for prov, names_ in acts.items():
            fun = '{0}.reboot'.format(prov)
            for name in names_:
                self.clouds[fun](name)

    def create(self, vm_):
        '''
        Create a single VM
        '''
        if 'minion' in vm_ and vm_['minion'] is None:
            vm_['minion'] = {}
        fun = '{0}.create'.format(self.provider(vm_))
        if fun not in self.clouds:
            log.error(
                'Public cloud provider {0} is not available'.format(
                    self.provider(vm_)
                )
            )
            return

        priv, pub = saltcloud.utils.gen_keys(
            saltcloud.utils.get_option('keysize', self.opts, vm_)
        )
        vm_['pub_key'] = pub
        vm_['priv_key'] = priv

        if 'make_master' in vm_ and vm_['make_master'] is True:
            master_priv, master_pub = saltcloud.utils.gen_keys(
                saltcloud.utils.get_option('keysize', self.opts, vm_)
            )
            vm_['master_pub'] = master_pub
            vm_['master_pem'] = master_priv

        if 'script' in self.opts:
            vm_['os'] = self.opts['script']
        if 'script' in vm_:
            vm_['os'] = vm_['script']

        saltcloud.utils.accept_key(self.opts['pki_dir'], pub, vm_['name'])
        try:
            self.clouds['{0}.create'.format(self.provider(vm_))](vm_)
        except KeyError as exc:
            log.error(
                'Failed to create VM {0}. Configuration value {1} needs '
                'to be set'.format(
                    vm_['name'], exc
                )
            )

    def profile_provider(self, profile=None):
        for definition in self.opts['vm']:
            if definition['profile'] == profile:
                if 'provider' in definition:
                    return definition['provider']
                else:
                    return self.opts['provider']

    def run_profile(self):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        pmap = self.map_providers()

        current_boxen = {}
        for provider in pmap:
            for box in pmap[provider]:
                current_boxen[box] = provider

        found = False
        for name in self.opts['names']:
            for vm_ in self.opts['vm']:
                if vm_['profile'] == self.opts['profile']:
                    # It all checks out, make the VM
                    found = True
                    if name in current_boxen:
                        # The specified VM already exists, don't make it anew
                        log.warn(
                            '{0} already exists on {1}'.format(
                                name, current_boxen[name]
                            )
                        )
                        continue
                    vm_['name'] = name
                    if self.opts['parallel']:
                        multiprocessing.Process(
                            target=lambda: self.create(vm_),
                        ).start()
                    else:
                        self.create(vm_)
        if not found:
            log.error(
                'Profile {0} is not defined'.format(self.opts['profile'])
            )

    def do_action(self, names, kwargs):
        '''
        Perform an action which may be specific to this cloud provider
        '''
        pmap = self.map_providers()

        current_boxen = {}
        for provider in pmap:
            for box in pmap[provider]:
                current_boxen[box] = provider

        acts = {}
        for prov, nodes in pmap.items():
            acts[prov] = []
            for node in nodes:
                if node in names:
                    acts[prov].append(node)

        completed = []
        for prov, names_ in acts.items():
            for name in names:
                if name in names_:
                    fun = '{0}.{1}'.format(prov, self.opts['action'])
                    if kwargs:
                        self.clouds[fun](name, kwargs, call='action')
                    else:
                        self.clouds[fun](name, call='action')
                    completed.append(name)

        for name in names:
            if name not in completed:
                print('{0} was not found, not running {1} action'.format(
                    name, self.opts['action'])
                )


    def do_function(self, prov, func, kwargs):
        '''
        Perform an action which may be specific to this cloud provider
        '''
        fun = '{0}.{1}'.format(prov, func)
        if kwargs:
            self.clouds[fun](call='function', kwargs=kwargs)
        else:
            self.clouds[fun](call='function')


class Map(Cloud):
    '''
    Create a VM stateful map execution object
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
            if provider is None:
                log.info(
                    'No provider for the mapped {0!r} profile was '
                    'found.'.format(
                        profile
                    )
                )
                continue
            vms = [i.keys() if type(i) == dict else [i] for i in vmap]
            vms = [item for sublist in vms for item in sublist]
            for vm in vms:
                if provider not in full_map:
                    full_map[provider] = {}

                if vm in query_map[provider]:
                    full_map[provider][vm] = query_map[provider][vm]
                else:
                    full_map[provider][vm] = 'Absent'
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
            raise ValueError(
                'The specified map file does not exist: {0}\n'.format(
                    self.opts['map']
                )
            )
        try:
            with open(self.opts['map'], 'rb') as fp_:
                try:
                    #open mako file
                    temp_ = Template(open(fp_, 'r').read())
                    #render as yaml
                    map_ = temp_.render()
                except:
                    map_ = yaml.load(fp_.read())
        except Exception as exc:
            log.error(
                'Rendering map {0} failed, render error:\n{1}'.format(
                    self.opts['map'], exc
                )
            )
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
            if self.opts['enable_hard_maps'] is True:
                # Look for the items to delete
                ret['destroy'] = exist.difference(defined)
            else:
                print('The --hard map can be extremely dangerous to use, and '
                      'therefore must explicitly be enabled in the main'
                      'configuration file, by setting enable_hard_maps to '
                      'True')
                sys.exit(1)
        return ret

    def run_map(self, dmap):
        '''
        Execute the contents of the VM map
        '''
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
                        if 'volumes' in miniondict[name]:
                            tvm['map_volumes'] = miniondict[name]['volumes']
            if self.opts['parallel']:
                multiprocessing.Process(
                    target=lambda: self.create(tvm)
                ).start()
            else:
                self.create(tvm)
        for name in dmap.get('destroy', set()):
            self.destroy(name)
