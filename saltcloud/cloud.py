'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''
# Import python libs
import os
import copy
import glob
import multiprocessing
import logging
import time

# Import saltcloud libs
import saltcloud.utils
import saltcloud.loader
import saltcloud.config as config
from saltcloud.exceptions import (
    SaltCloudNotFound,
    SaltCloudSystemExit,
    SaltCloudConfigError
)

# Import salt libs
import salt.client
import salt.utils

# Import third party libs
import yaml

# Get logging started
log = logging.getLogger(__name__)

try:
    from mako.template import Template
except ImportError:
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
        provider = vm_['provider']
        if ':' in provider:
            # We have the alias and the provider
            # Return the provider
            alias, provider = provider.split(':')
            return provider

        try:
            # There's no <alias>:<provider> entry, return the first one if
            # defined
            if provider in self.opts['providers']:
                return self.opts['providers'][provider][0]['provider']
        except Exception, err:
            log.error(
                'Failed to get the proper cloud provider. '
                'Error: {0}'.format(err),
                # Show the traceback if the debug logging level is enabled
                exc_info=log.isEnabledFor(logging.DEBUG)
            )

        # Let's try, as a last resort, to get the provider from self.opts
        if 'provider' in self.opts:
            if '{0}.create'.format(self.opts['provider']) in self.clouds:
                return self.opts['provider']

    def get_providers(self):
        '''
        Return the providers configured within the VM settings.
        '''
        provs = set()
        for fun in self.clouds:
            if not '.' in fun:
                continue
            provs.add(fun[:fun.index('.')])
        return provs

    def build_lookup(self, lookup):
        if lookup == 'all':
            providers = []
            for alias, entries in self.opts['providers'].iteritems():
                for entry in entries:
                    provider = entry.get('provider', None)
                    if provider is not None and provider not in providers:
                        providers.append(provider)

            if not providers:
                raise SaltCloudSystemExit(
                    'There are now cloud providers configured'
                )

            return providers

        if ':' in lookup:
            alias, provider = lookup.split(':')
            if alias not in self.opts['providers']:
                raise SaltCloudSystemExit(
                    'No cloud providers matched {0!r}. Available: {1}'.format(
                        lookup, ', '.join(self.opts['providers'].keys())
                    )
                )

            for entry in self.opts['providers'].get(alias):
                if entry.get('provider', None) == provider:
                    return [provider]

            raise SaltCloudSystemExit(
                'No cloud providers matched {0!r}. Available: {1}'.format(
                    lookup, ', '.join(self.opts['providers'].keys())
                )
            )

        providers = [
            d.get('provider', None) for d in
            self.opts['providers'].get(lookup, [{}])
            if d and d.get('provider', None) is not None
        ]
        if not providers:
            raise SaltCloudSystemExit(
                'No cloud providers matched {0!r}. '
                'Available selections: {1}'.format(
                    lookup, ', '.join(self.opts['providers'].keys())
                )
            )
        return providers


    def map_providers(self, query='list_nodes'):
        '''
        Return a mapping of what named VMs are running on what VM providers
        based on what providers are defined in the configuration and VMs
        '''
        provs = self.get_providers()
        pmap = {}
        for prov in provs:
            fun = '{0}.{1}'.format(prov, query)
            if fun not in self.clouds:
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

        lookups = self.build_lookup(lookup)
        if not lookups:
            return locations

        for prov in provs:
            # If all providers are not desired, then don't get them
            if prov not in lookups:
                continue

            fun = '{0}.avail_locations'.format(prov)
            if fun not in self.clouds:
                # The capability to gather locations is not supported by this
                # cloud module
                continue
            try:
                locations[prov] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err,
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
        return locations

    def image_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        provs = self.get_providers()
        images = {}

        lookups = self.build_lookup(lookup)
        if not lookups:
            return images

        for prov in provs:
            # If all providers are not desired, then don't get them
            if prov not in lookups:
                continue

            fun = '{0}.avail_images'.format(prov)
            if not fun in self.clouds:
                # The capability to gather images is not supported by this
                # cloud module
                continue
            try:
                images[prov] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err,
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
        return images

    def size_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        provs = self.get_providers()
        sizes = {}

        lookups = self.build_lookup(lookup)
        if not lookups:
            return sizes

        for prov in provs:
            # If all providers are not desired, then don't get them
            if prov not in lookups:
                continue

            fun = '{0}.avail_sizes'.format(prov)
            if not fun in self.clouds:
                # The capability to gather sizes is not supported by this
                # cloud module
                continue
            try:
                sizes[prov] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err,
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
        return sizes

    def provider_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        provs = self.get_providers()
        prov_list = {}

        lookups = self.build_lookup(lookup)
        if not lookups:
            return prov_list

        for prov in provs:
            if prov not in lookups:
                continue

            prov_list[prov] = {}
        return prov_list

    def create_all(self):
        '''
        Create/Verify the VMs in the VM data
        '''
        ret = []

        for vm_ in self.opts['vm']:
            ret.append(
                {vm_['name']: self.create(vm_)}
            )

        return ret

    def destroy(self, names):
        '''
        Destroy the named VMs
        '''
        ret = []

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
                delret = self.clouds[fun](name)
                ret.append({name: delret})

                if not delret:
                    continue

                key_file = os.path.join(
                    self.opts['pki_dir'], 'minions', name
                )
                globbed_key_file = glob.glob('{0}.*'.format(key_file))

                if not os.path.isfile(key_file) and not globbed_key_file:
                    # There's no such key file!? It might have been renamed
                    if isinstance(delret, dict) and 'newname' in delret:
                        saltcloud.utils.remove_key(
                            self.opts['pki_dir'], delret['newname']
                        )
                    continue

                if os.path.isfile(key_file) and not globbed_key_file:
                    # Single key entry. Remove it!
                    saltcloud.utils.remove_key(self.opts['pki_dir'], name)
                    continue

                if not os.path.isfile(key_file) and globbed_key_file:
                    # Since we have globbed matches, there are probably
                    # some keys for which their minion configuration has
                    # append_domain set.
                    if len(globbed_key_file) == 1:
                        # Single entry, let's remove it!
                        saltcloud.utils.remove_key(
                            self.opts['pki_dir'],
                            os.path.basename(globbed_key_file[0])
                        )
                        continue

                # Since we can't get the profile or map entry used to create
                # the VM, we can't also get the append_domain setting.
                # And if we reached this point, we have several minion keys
                # who's name starts with the machine name we're deleting.
                # We need to ask one by one!?
                print(
                    'There are several minion keys who\'s name starts '
                    'with {0!r}. We need to ask you which one should be '
                    'deleted:'.format(
                        name
                    )
                )
                while True:
                    for idx, filename in enumerate(globbed_key_file):
                        print(' {0}: {1}'.format(
                            idx, os.path.basename(filename)
                        ))
                    selection = raw_input(
                        'Which minion key should be deleted(number)? '
                    )
                    try:
                        selection = int(selection)
                    except ValueError:
                        print(
                            '{0!r} is not a valid selection.'.format(selection)
                        )

                    try:
                        filename = os.path.basename(
                            globbed_key_file.pop(selection)
                        )
                    except:
                        continue

                    delete = raw_input(
                        'Delete {0!r}? [Y/n]? '.format(filename)
                    )
                    if delete == '' or delete.lower().startswith('y'):
                        saltcloud.utils.remove_key(
                            self.opts['pki_dir'], filename
                        )
                        print('Deleted {0!r}'.format(filename))
                        break

                    print('Did not delete {0!r}'.format(filename))
                    break

        return ret

    def reboot(self, names):
        '''
        Reboot the named VMs
        '''
        ret = []
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
                ret.append({
                    name: self.clouds[fun](name)
                })

        return ret

    def create(self, vm_):
        '''
        Create a single VM
        '''
        output = {}

        minion_dict = config.get_config_value(
            'minion', vm_, self.opts, default={}
        )

        fun = '{0}.create'.format(self.provider(vm_))
        if fun not in self.clouds:
            log.error(
                'Public cloud provider {0} is not available'.format(
                    self.provider(vm_)
                )
            )
            return

        deploy = config.get_config_value('deploy', vm_, self.opts)

        if deploy is True and 'master' not in minion_dict:
            raise SaltCloudConfigError(
                'There\'s no master defined on the {0!r} VM settings'.format(
                    vm_['name']
                )
            )

        priv, pub = saltcloud.utils.gen_keys(
            config.get_config_value('keysize', vm_, self.opts)
        )
        vm_['pub_key'] = pub
        vm_['priv_key'] = priv

        if config.get_config_value('make_master', vm_, self.opts):
            master_priv, master_pub = saltcloud.utils.gen_keys(
                config.get_config_value('keysize', vm_, self.opts)
            )
            vm_['master_pub'] = master_pub
            vm_['master_pem'] = master_priv

        vm_['os'] = config.get_config_value('script', vm_, self.opts)

        key_id = vm_['name']

        if 'append_domain' in minion_dict:
            key_id = '.'.join([key_id, minion_dict['append_domain']])

        saltcloud.utils.accept_key(self.opts['pki_dir'], pub, key_id)

        try:
            output = self.clouds['{0}.create'.format(self.provider(vm_))](vm_)

            if output is not False and 'sync_after_install' in self.opts:
                if self.opts['sync_after_install'] not in (
                        'all', 'modules', 'states', 'grains'):
                    log.error('Bad option for sync_after_install')
                    return output

                # a small pause makes the sync work reliably
                time.sleep(3)
                client = salt.client.LocalClient()
                ret = client.cmd(vm_['name'], 'saltutil.sync_{0}'.format(
                    self.opts['sync_after_install']
                ))
                log.info('Synchronized the following dynamic modules:')
                log.info('  {0}'.format(ret))
        except KeyError as exc:
            log.exception(
                'Failed to create VM {0}. Configuration value {1} needs '
                'to be set'.format(
                    vm_['name'], exc
                )
            )

        return output

    def profile_provider(self, profile=None):
        for definition in self.opts['vm']:
            if definition['profile'] != profile:
                continue

            if 'provider' in definition:
                provider = definition['provider']
                if ':' in provider:
                    # We have the alias and the provider
                    # Return the provider
                    alias, provider = provider.split(':')
                    return provider

                # There's no <alias>:<provider> entry, return the first one
                return self.opts['providers'][provider][0]['provider']

            return self.opts['provider']

    def run_profile(self):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        ret = {}
        pmap = self.map_providers()
        found = False
        for name in self.opts['names']:
            for vm_ in self.opts['vm']:
                vm_profile = vm_['profile']
                if vm_profile != self.opts['profile']:
                    continue

                # It all checks out, make the VM
                found = True
                provider = self.profile_provider(vm_profile)
                boxes = pmap[provider]
                if name in boxes and \
                        boxes[name]['state'].lower() != 'terminated':
                    # The specified VM already exists, don't make a new one
                    msg = '{0} already exists on {1}'.format(
                        name, provider
                    )
                    log.error(msg)
                    ret[name] = {'Error': msg}
                    continue

                vm_['name'] = name
                if self.opts['parallel']:
                    process = multiprocessing.Process(
                        target=self.create,
                        args=(vm_,)
                    )
                    process.start()
                    ret[name] = {
                        'Provisioning': 'VM being provisioned in parallel. '
                                        'PID: {0}'.format(process.pid)
                    }
                    continue

                ret[name] = self.create(vm_)

        if not found:
            msg = 'Profile {0} is not defined'.format(self.opts['profile'])
            ret['Error'] = msg
            log.error(msg)

        return ret

    def do_action(self, names, kwargs):
        '''
        Perform an action on a VM which may be specific to this cloud provider
        '''
        pmap = self.map_providers()

        ret = {}

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

        ret = {}
        completed = []
        for prov, names_ in acts.items():
            for name in names:
                if name in names_:
                    fun = '{0}.{1}'.format(prov, self.opts['action'])
                    if kwargs:
                        ret[name] = self.clouds[fun](
                            name, kwargs, call='action'
                        )
                    else:
                        ret[name] = self.clouds[fun](name, call='action')
                    completed.append(name)

        for name in names:
            if name not in completed:
                print('{0} was not found, not running {1} action'.format(
                    name, self.opts['action'])
                )

        return ret

    def do_function(self, func, prov, kwargs):
        '''
        Perform a function against a cloud provider
        '''
        fun = '{0}.{1}'.format(prov, func)
        if kwargs:
            ret = self.clouds[fun](call='function', kwargs=kwargs)
        else:
            ret = self.clouds[fun](call='function')

        return ret


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
        if self.opts.get('map', None) is None:
            return {}

        if not os.path.isfile(self.opts['map']):
            raise SaltCloudNotFound(
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
                    #FIXME: what about other providers?
                    if prov != 'aws' or pmap['aws'][name]['state'] != 2:
                        ret['create'].pop(name)
        if self.opts['hard']:
            if self.opts['enable_hard_maps'] is True:
                # Look for the items to delete
                ret['destroy'] = exist.difference(defined)
            else:
                raise SaltCloudSystemExit(
                    'The --hard map can be extremely dangerous to use, '
                    'and therefore must explicitly be enabled in the main '
                    'configuration file, by setting \'enable_hard_maps\' '
                    'to True'
                )
        return ret

    def run_map(self, dmap):
        '''
        Execute the contents of the VM map
        '''
        output = {}
        if self.opts['parallel']:
            parallel_data = []
        master_name = None
        master_host = None
        try:
            master_name, master_profile = (
                (name, profile) for name, profile in dmap['create'].items()
                if 'make_master' in profile and
                profile['make_master'] is True
            ).next()
            log.debug('Creating new master {0}'.format(master_name))
            tvm = self.vm_options(master_name,
                                  master_profile,
                                  None,
                                  ['grains', 'volumes'])
            out = self.create(tvm)
            if 'deploy_kwargs' in out and 'host' in out['deploy_kwargs']:
                master_host = out['deploy_kwargs']['host']
                output[master_name] = out
            else:
                raise SaltCloudSystemExit(
                    'Host for new master {0} was not found, '
                    'aborting map'.format(
                        master_name
                    )
                )
        except StopIteration:
            log.debug('No make_master found in map')

        # Generate the fingerprint of the master pubkey in
        #     order to mitigate man-in-the-middle attacks
        master_pub = self.opts['pki_dir'] + '/master.pub'
        master_finger = ''
        if os.path.isfile(master_pub) and hasattr(salt.utils, 'pem_finger'):
            master_finger = salt.utils.pem_finger(master_pub)

        option_types = ['grains', 'minion', 'volumes']
        for name, profile in dmap['create'].items():
            if master_name and name is master_name:
                continue
            if master_host and 'master' not in profile['minion']:
                profile['minion']['master'] = master_host
            tvm = self.vm_options(name, profile, master_finger, option_types)
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
                for myvar in miniondict[name]:
                    if myvar not in ('grains', 'minion', 'volumes'):
                        tvm[myvar] = miniondict[name][myvar]
            if 'minion' not in tvm:
                tvm['minion'] = tvm['map_minion']
            if self.opts['parallel']:
                parallel_data.append({
                    'opts': self.opts,
                    'name': name,
                    'profile': tvm,
                })
            else:
                output[name] = self.create(tvm)
        for name in dmap.get('destroy', set()):
            output[name] = self.destroy(name)
        if self.opts['parallel'] and len(parallel_data) > 0:
            output_multip = multiprocessing.Pool(len(parallel_data)).map(
                func=create_multiprocessing,
                iterable=parallel_data
            )
            for obj in output_multip:
                output.update(obj)
        return output

    def vm_options(self, name, profile, master_finger, option_types):
        tvm = copy.deepcopy(profile)
        tvm['name'] = name
        tvm['master_finger'] = master_finger
        for miniondict in self.map[tvm['profile']]:
            if isinstance(miniondict, dict) and name in miniondict:
                for option in option_types:
                    if option in miniondict[name]:
                        tvm['map_{0}'.format(option)] = miniondict[name][option]
        return tvm


def create_multiprocessing(config):
    '''
    This function will be called from another process when running a map in
    parallel mode. The result from the create is always a json object.
    '''
    config['opts']['output'] = 'json'
    cloud = Cloud(config['opts'])
    output = cloud.create(config['profile'])
    return {config['name']: output}
