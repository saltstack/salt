'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''
# Import python libs
import os
import glob
import time
import signal
import logging
import tempfile
import multiprocessing

# Import saltcloud libs
import saltcloud.utils
import saltcloud.loader
import saltcloud.config as config
from saltcloud.exceptions import (
    SaltCloudNotFound,
    SaltCloudException,
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

    def get_configured_providers(self):
        providers = set()
        for alias, entries in self.opts['providers'].iteritems():
            for entry in entries:
                provider = entry.get('provider', None)
                if provider is None:
                    log.warn(
                        'There\'s a configured provider under {0} lacking the '
                        '\'provider\' required configuration setting.'.format(
                            alias
                        )
                    )
                    continue
                if provider is not None and alias not in providers:
                    providers.add(alias)
        return providers

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
                    'There are no cloud providers configured.'
                )

            return providers

        if ':' in lookup:
            alias, provider = lookup.split(':')
            if alias not in self.opts['providers']:
                raise SaltCloudSystemExit(
                    'No cloud providers matched {0!r}. Available: {1}'.format(
                        lookup, ', '.join(self.get_configured_providers())
                    )
                )

            for entry in self.opts['providers'].get(alias):
                if entry.get('provider', None) == provider:
                    return [provider]

            raise SaltCloudSystemExit(
                'No cloud providers matched {0!r}. Available: {1}'.format(
                    lookup, ', '.join(self.get_configured_providers())
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
                    lookup, ', '.join(self.get_configured_providers())
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

    def map_providers_parallel(self, query='list_nodes'):
        '''
        Return a mapping of what named VMs are running on what VM providers
        based on what providers are defined in the configuration and VMs

        Same as map_providers but query in parallel.
        '''
        providers = self.get_providers()

        opts = self.opts.copy()
        multiprocessing_data = []
        for provider in providers:
            fun = '{0}.{1}'.format(provider, query)
            if fun not in self.clouds:
                log.error(
                    'Public cloud provider {0} is not available'.format(
                        provider
                    )
                )
                continue
            multiprocessing_data.append({
                'fun': fun,
                'opts': opts,
                'query': query,
                'provider': provider
            })

        output = {}
        providers_count = len(providers)
        pool = multiprocessing.Pool(
            providers_count < 10 and providers_count or 10,
            init_pool_worker
        )
        try:
            parallel_pmap = pool.map(
                func=run_parallel_map_providers_query,
                iterable=multiprocessing_data
            )
        except KeyboardInterrupt:
            print 'Caught KeyboardInterrupt, terminating workers'
            pool.terminate()
            pool.join()
            raise SaltCloudSystemExit('Keyboard Interrupt caught')
        else:
            pool.close()
            pool.join()

        for obj in parallel_pmap:
            output.update(obj)
        return output

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
                log.debug(
                    'The {0!r} cloud provider is unable to get the locations '
                    'information'.format(prov)
                )
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
                log.debug(
                    'The {0!r} cloud provider is unable to get the images '
                    'information'.format(prov)
                )
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
                log.debug(
                    'The {0!r} cloud provider is unable to get the sizes '
                    'information'.format(prov)
                )
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
        names = set(names)

        pmap = self.map_providers_parallel()
        dels = {}
        for prov, nodes in pmap.items():
            dels[prov] = []
            for node in nodes:
                if node in names:
                    dels[prov].append(node)
                    names.remove(node)

        for prov, names_ in dels.items():
            fun = '{0}.destroy'.format(prov)
            for name in names_:
                delret = self.clouds[fun](name)
                ret.append({name: (True, delret)})

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

        # This machine was asked to be destroyed but could not be found
        for name in names:
            ret.append({name: False})

        if not ret:
            raise SaltCloudSystemExit('No machines were destroyed!')

        return ret

    def reboot(self, names):
        '''
        Reboot the named VMs
        '''
        ret = []
        pmap = self.map_providers_parallel()
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

    def create(self, vm_, local_master=True):
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
        make_master = config.get_config_value('make_master', vm_, self.opts)

        if deploy is True and make_master is False and \
                'master' not in minion_dict:
            raise SaltCloudConfigError(
                'There\'s no master defined on the {0!r} VM settings'.format(
                    vm_['name']
                )
            )

        if deploy is True and 'pub_key' not in vm_ and 'priv_key' not in vm_:
            log.debug('Generating minion keys for {0[name]!r}'.format(vm_))
            priv, pub = saltcloud.utils.gen_keys(
                config.get_config_value('keysize', vm_, self.opts)
            )
            vm_['pub_key'] = pub
            vm_['priv_key'] = priv

        key_id = minion_dict.get('id', vm_['name'])

        if 'append_domain' in minion_dict:
            key_id = '.'.join([key_id, minion_dict['append_domain']])

        if make_master is True:
            if 'master_pub' not in vm_ and 'master_pem' not in vm_:
                log.debug(
                    'Generating the master keys for {0[name]!r}'.format(
                        vm_
                    )
                )
                master_priv, master_pub = saltcloud.utils.gen_keys(
                    config.get_config_value('keysize', vm_, self.opts)
                )
                vm_['master_pub'] = master_pub
                vm_['master_pem'] = master_priv
        elif local_master is True and deploy is True:
            # Since we're not creating a master, and we're deploying, accept
            # the key on the local master
            saltcloud.utils.accept_key(
                self.opts['pki_dir'], vm_['pub_key'], key_id
            )

        vm_['os'] = config.get_config_value('script', vm_, self.opts)

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

                if provider not in self.opts['providers']:
                    # We do not know the provider, send the one, if any,
                    # specified from CLI
                    if 'provider' in self.opts:
                        return self.opts['provider']

                    raise SaltCloudSystemExit(
                        'The {0!r} provider is not known'.format(provider)
                    )

                # There's no <alias>:<provider> entry, return the first one
                return self.opts['providers'][provider][0]['provider']

            return self.opts['provider']

    def run_profile(self):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        ret = {}
        pmap = self.map_providers_parallel()
        found = False
        for name in self.opts['names']:
            for vm_ in self.opts['vm']:
                vm_profile = vm_['profile']
                if vm_profile != self.opts['profile']:
                    continue

                # It all checks out, make the VM
                found = True
                provider = self.profile_provider(vm_profile)
                if provider not in pmap:
                    ret[name] = {
                        'Error': 'The defined profile provider {0!r} was not '
                                 'found.'.format(vm_['provider'])
                    }
                    continue

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

                try:
                    ret[name] = self.create(vm_)
                    if self.opts.get('show_deploy_args', False) is False:
                        ret[name].pop('deploy_kwargs', None)
                except (SaltCloudSystemExit, SaltCloudConfigError), exc:
                    if len(self.opts['names']) == 1:
                        raise
                    ret['name'] = {'Error': exc.message}

        if not found:
            msg = 'Profile {0} is not defined'.format(self.opts['profile'])
            ret['Error'] = msg
            log.error(msg)

        return ret

    def do_action(self, names, kwargs):
        '''
        Perform an action on a VM which may be specific to this cloud provider
        '''
        pmap = self.map_providers_parallel()

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
                    if fun not in self.clouds:
                        # The cloud provider does not provide the action
                        continue
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

    def do_function(self, prov, func, kwargs):
        '''
        Perform a function against a cloud provider
        '''
        fun = '{0}.{1}'.format(prov, func)
        log.debug(
            'Trying to execute {0!r} with the following kwargs: {1}'.format(
                fun, kwargs
            )
        )
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
        query_map = self.map_providers_parallel(query=query)
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
            for vm in [vm.get('name') for vm in vmap]:
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
                    # open mako file
                    temp_ = Template(open(fp_, 'r').read())
                    # render as yaml
                    map_ = temp_.render()
                except:
                    map_ = yaml.load(fp_.read())
        except Exception as exc:
            log.error(
                'Rendering map {0} failed, render error:\n{1}'.format(
                    self.opts['map'], exc
                ),
                exc_info=log.isEnabledFor(logging.DEBUG)
            )
            return {}

        if 'include' in map_:
            map_ = salt.config.include_config(map_, self.opts['map'])

        # Create expected data format if needed
        for profile, mapped in map_.copy().items():
            if isinstance(mapped, (list, tuple)):
                entries = []
                for mapping in mapped:
                    if isinstance(mapping, basestring):
                        # Foo:
                        #   - bar1
                        #   - bar2
                        mapping = {mapping: None}
                    for name, overrides in mapping.iteritems():
                        if overrides is None:
                            # Foo:
                            #   - bar1:
                            #   - bar2:
                            overrides = {}
                        overrides.setdefault('name', name)
                        entries.append(overrides)
                map_[profile] = entries
                continue

            if isinstance(mapped, dict):
                # Convert the dictionary mapping to a list of dictionaries
                # Foo:
                #  bar1:
                #    grains:
                #      foo: bar
                #  bar2:
                #    grains:
                #      foo: bar
                entries = []
                for name, overrides in mapped.iteritems():
                    overrides.setdefault('name', name)
                    entries.append(overrides)
                map_[profile] = entries
                continue

            if isinstance(mapped, basestring):
                # If it's a single string entry, let's make iterable because of
                # the next step
                mapped = [mapped]

            map_[profile] = [{'name': name} for name in mapped]
        return map_

    def map_data(self):
        '''
        Create a data map of what to execute on
        '''
        ret = {}
        pmap = self.map_providers_parallel()
        ret['create'] = {}
        exist = set()
        defined = set()
        for profile in self.map:
            pdata = {}
            for pdef in self.opts['vm']:
                # The named profile does not exist
                if pdef.get('profile', None) == profile:
                    pdata = pdef

            if not pdata:
                continue

            for overrides in self.map[profile]:
                # Get the VM name
                nodename = overrides.get('name')
                nodedata = pdata.copy()
                # Update profile data with the map overrides
                for setting in ('grains', 'master', 'minion', 'volumes'):
                    deprecated = 'map_{0}'.format(setting)
                    if deprecated in overrides:
                        log.warn(
                            'The use of {0!r} on the {1!r} mapping has '
                            'been deprecated. The preferred way now is to '
                            'just define {2!r}. For now, salt-cloud will do '
                            'the proper thing and convert the deprecated '
                            'mapping into the preferred one.'.format(
                                deprecated, nodename, setting
                            )
                        )
                        overrides[setting] = overrides.pop(deprecated)
                nodedata.update(overrides)
                # Add the computed information to the return data
                ret['create'][nodename] = nodedata
                # Add the node name to the defined set
                defined.add(nodename)

        for prov in pmap:
            for name in pmap[prov]:
                exist.add(name)
                if name not in ret['create']:
                    continue

                # FIXME: what about other providers?
                if prov in ('aws', 'ec2'):
                    if ('aws' in pmap and
                            pmap['aws'][name]['state'] != 'TERMINATED') or (
                            'ec2' in pmap and
                            pmap['ec2'][name]['state'] != 'TERMINATED'):
                        log.info(
                            '{0!r} already exists, removing from the '
                            'create map'.format(name)
                        )
                        ret['create'].pop(name)
                    continue

                # Regarding other providers, simply remove them for the create
                # map.
                log.warn(
                    '{0!r} already exists, removing from the '
                    'create map'.format(name)
                )
                ret['create'].pop(name)

        if self.opts['hard']:
            if self.opts['enable_hard_maps'] is False:
                raise SaltCloudSystemExit(
                    'The --hard map can be extremely dangerous to use, '
                    'and therefore must explicitly be enabled in the main '
                    'configuration file, by setting \'enable_hard_maps\' '
                    'to True'
                )

            # Hard maps are enabled, Look for the items to delete.
            ret['destroy'] = exist.difference(defined)
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
        master_finger = None
        try:
            master_name, master_profile = (
                (name, profile) for name, profile in dmap['create'].items()
                if profile.get('make_master', False) is True
            ).next()
            log.debug('Creating new master {0!r}'.format(master_name))
            if config.get_config_value('deploy',
                                       master_profile,
                                       self.opts) is False:
                raise SaltCloudSystemExit(
                    'Cannot proceed with \'make_master\' when salt deployment '
                    'is disabled(ex: --no-deploy).'
                )

            # Generate the master keys
            log.debug(
                'Generating master keys for {0[name]!r}'.format(master_profile)
            )
            priv, pub = saltcloud.utils.gen_keys(
                config.get_config_value('keysize', master_profile, self.opts)
            )
            master_profile['master_pub'] = pub
            master_profile['master_pem'] = priv

            # Generate the fingerprint of the master pubkey in order to
            # mitigate man-in-the-middle attacks
            master_temp_pub = salt.utils.mkstemp()
            with salt.utils.fopen(master_temp_pub, 'w') as mtp:
                mtp.write(pub)
            master_finger = salt.utils.pem_finger(master_temp_pub)
            os.unlink(master_temp_pub)

            if master_profile.get('make_minion', True) is True:
                master_profile.setdefault('minion', {})
                # Set this minion's master as local if the user has not set it
                master_profile['minion'].setdefault('master', '127.0.0.1')
                if master_finger is not None:
                    master_profile['master_finger'] = master_finger

            # Generate the minion keys to pre-seed the master:
            for name, profile in dmap['create'].iteritems():
                make_minion = config.get_config_value(
                    'make_minion', profile, self.opts, default=True
                )
                if make_minion is False:
                    continue

                log.debug(
                    'Generating minion keys for {0[name]!r}'.format(profile)
                )
                priv, pub = saltcloud.utils.gen_keys(
                    config.get_config_value('keysize', profile, self.opts)
                )
                profile['pub_key'] = pub
                profile['priv_key'] = priv
                # Store the minion's public key in order to be pre-seeded in
                # the master
                master_profile.setdefault('preseed_minion_keys', {})
                master_profile['preseed_minion_keys'].update({name: pub})

            out = self.create(master_profile, local_master=False)
            if not isinstance(out, dict):
                log.debug(
                    'Master creation details is not a dictionary: {0}'.format(
                        out
                    )
                )

            deploy_kwargs = (
                self.opts.get('show_deploy_args', False) is True and
                # Get the needed data
                out.get('deploy_kwargs', {}) or
                # Strip the deploy_kwargs from the returned data since we don't
                # want it shown in the console.
                out.pop('deploy_kwargs', {})
            )

            master_host = deploy_kwargs.get('host', None)
            if master_host is None:
                raise SaltCloudSystemExit(
                    'Host for new master {0} was not found, '
                    'aborting map'.format(
                        master_name
                    )
                )
            output[master_name] = out
        except StopIteration:
            log.debug('No make_master found in map')
            # Local master?
            # Generate the fingerprint of the master pubkey in order to
            # mitigate man-in-the-middle attacks
            master_pub = os.path.join(self.opts['pki_dir'], 'master.pub')
            if os.path.isfile(master_pub):
                master_finger = salt.utils.pem_finger(master_pub)

        opts = self.opts.copy()
        if self.opts['parallel']:
            # Force display_ssh_output to be False since the console will
            # need to be reset afterwards
            log.info(
                'Since parallel deployment is in use, ssh console output '
                'is disabled. All ssh output will be logged though'
            )
            opts['display_ssh_output'] = False

        for name, profile in dmap['create'].items():
            if name == master_name:
                # Already deployed, it's the master's minion
                continue

            if master_finger is not None:
                profile['master_finger'] = master_finger

            if master_host is not None:
                profile.setdefault('minion', {})
                profile['minion'].setdefault('master', master_host)

            if self.opts['parallel']:
                parallel_data.append({
                    'opts': opts,
                    'name': name,
                    'profile': profile,
                    'local_master': master_name is None
                })
                continue

            # Not deploying in parallel
            try:
                output[name] = self.create(
                    profile, local_master=master_name is None
                )
                if self.opts.get('show_deploy_args', False) is False:
                    output[name].pop('deploy_kwargs', None)
            except SaltCloudException as exc:
                log.error(
                    'Failed to deploy {0!r}. Error: {1}'.format(
                        name, exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
                output[name] = {'Error': str(exc)}

        for name in dmap.get('destroy', ()):
            output[name] = self.destroy(name)

        if self.opts['parallel'] and len(parallel_data) > 0:
            output_multip = multiprocessing.Pool(len(parallel_data)).map(
                func=create_multiprocessing,
                iterable=parallel_data
            )
            for obj in output_multip:
                output.update(obj)

        return output


def init_pool_worker():
    '''
    Make every worker ignore KeyboarInterrup's since it will be handled by the
    parent process.
    '''
    signal.signal(signal.SIGINT, signal.SIG_IGN)


def create_multiprocessing(parallel_data):
    '''
    This function will be called from another process when running a map in
    parallel mode. The result from the create is always a json object.
    '''
    parallel_data['opts']['output'] = 'json'
    cloud = Cloud(parallel_data['opts'])
    try:
        output = cloud.create(
            parallel_data['profile'],
            local_master=parallel_data['local_master']
        )
    except SaltCloudException as exc:
        log.error(
            'Failed to deploy {0[name]!r}. Error: {1}'.format(
                parallel_data, exc
            ),
            # Show the traceback if the debug logging level is
            # enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        return {parallel_data['name']: {'Error': str(exc)}}

    if parallel_data['opts'].get('show_deploy_args', False) is False:
        output.pop('deploy_kwargs', None)

    return {
        parallel_data['name']: saltcloud.utils.simple_types_filter(output)
    }


def run_parallel_map_providers_query(data):
    '''
    This function will be called from another process when building the
    providers map.
    '''
    cloud = Cloud(data['opts'])
    try:
        return {
            data['provider']: saltcloud.utils.simple_types_filter(
                cloud.clouds[data['fun']]()
            )
        }
    except Exception:
        # Failed to communicate with the provider, don't list any
        # nodes
        return {data['provider']: []}
