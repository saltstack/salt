'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''
# Import python libs
import copy
import os
import glob
import time
import signal
import logging
import multiprocessing
from itertools import groupby

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
from salt.utils.verify import check_user

# Import third party libs
import yaml

# Get logging started
log = logging.getLogger(__name__)

try:
    from mako.template import Template
except ImportError:
    log.debug('Mako not available')


# Simple alias to improve code readability
CloudProviderContext = saltcloud.utils.CloudProviderContext


class Cloud(object):
    '''
    An object for the creation of new VMs
    '''
    def __init__(self, opts):
        self.opts = opts
        self.clouds = saltcloud.loader.clouds(self.opts)
        self.__switch_credentials()
        self.__filter_non_working_providers()
        self.__cached_provider_queries = {}

    def get_configured_providers(self):
        providers = set()
        for alias, drivers in self.opts['providers'].iteritems():
            if len(drivers) > 1:
                for driver in drivers:
                    providers.add('{0}:{1}'.format(alias, driver))
                continue
            providers.add(alias)
        return providers

    def lookup_providers(self, lookup):
        if lookup == 'all':
            providers = set()
            for alias, drivers in self.opts['providers'].iteritems():
                for driver in drivers:
                    providers.add((alias, driver))

            if not providers:
                raise SaltCloudSystemExit(
                    'There are no cloud providers configured.'
                )

            return providers

        if ':' in lookup:
            alias, driver = lookup.split(':')
            if alias not in self.opts['providers'] or \
                    driver not in self.opts['providers'][alias]:
                raise SaltCloudSystemExit(
                    'No cloud providers matched {0!r}. Available: {1}'.format(
                        lookup, ', '.join(self.get_configured_providers())
                    )
                )

            return set((alias, driver))

        providers = set()
        for alias, drivers in self.opts['providers'].iteritems():
            for driver in drivers:
                if lookup in (alias, driver):
                    providers.add((alias, driver))

        if not providers:
            raise SaltCloudSystemExit(
                'No cloud providers matched {0!r}. '
                'Available selections: {1}'.format(
                    lookup, ', '.join(self.get_configured_providers())
                )
            )
        return providers

    def map_providers(self, query='list_nodes', cached=False):
        '''
        Return a mapping of what named VMs are running on what VM providers
        based on what providers are defined in the configuration and VMs
        '''
        if cached is True and query in self.__cached_provider_queries:
            return self.__cached_provider_queries[query]

        pmap = {}
        for alias, drivers in self.opts['providers'].iteritems():
            for driver, details in drivers.iteritems():
                fun = '{0}.{1}'.format(driver, query)
                if fun not in self.clouds:
                    log.error(
                        'Public cloud provider {0} is not available'.format(
                            driver
                        )
                    )
                    continue
                if alias not in pmap:
                    pmap[alias] = {}

                try:
                    with CloudProviderContext(self.clouds[fun], alias, driver):
                        pmap[alias][driver] = self.clouds[fun]()
                except Exception as err:
                    log.debug(
                        'Failed to execute \'{0}()\' while querying for '
                        'running nodes: {1}'.format(fun, err),
                        # Show the traceback if the debug logging level is
                        # enabled
                        exc_info=log.isEnabledFor(logging.DEBUG)
                    )
                    # Failed to communicate with the provider, don't list any
                    # nodes
                    pmap[alias][driver] = []
        self.__cached_provider_queries[query] = pmap
        return pmap

    def map_providers_parallel(self, query='list_nodes', cached=False):
        '''
        Return a mapping of what named VMs are running on what VM providers
        based on what providers are defined in the configuration and VMs

        Same as map_providers but query in parallel.
        '''
        if cached is True and query in self.__cached_provider_queries:
            return self.__cached_provider_queries[query]

        opts = self.opts.copy()
        multiprocessing_data = []
        for alias, drivers in self.opts['providers'].iteritems():
            for driver, details in drivers.iteritems():
                fun = '{0}.{1}'.format(driver, query)
                if fun not in self.clouds:
                    log.error(
                        'Public cloud provider {0} is not available'.format(
                            driver
                        )
                    )
                    continue

                multiprocessing_data.append({
                    'fun': fun,
                    'opts': opts,
                    'query': query,
                    'alias': alias,
                    'driver': driver
                })

        output = {}
        data_count = len(multiprocessing_data)
        pool = multiprocessing.Pool(
            data_count < 10 and data_count or 10,
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

        for alias, driver, details in parallel_pmap:
            if not details:
                # There's no providers details?! Skip it!
                continue
            if alias not in output:
                output[alias] = {}
            output[alias][driver] = details

        self.__cached_provider_queries[query] = output
        return output

    def get_running_by_names(self, names, query='list_nodes', cached=False):
        if isinstance(names, basestring):
            names = [names]

        matches = {}
        handled_drivers = {}
        mapped_providers = self.map_providers_parallel(query, cached=cached)
        for alias, drivers in mapped_providers.iteritems():
            for driver, vms in drivers.iteritems():
                if driver not in handled_drivers:
                    handled_drivers[driver] = alias

                for vm_name, details in vms.iteritems():
                    # XXX: The logic bellow can be removed once the aws driver
                    # is removed
                    if vm_name not in names:
                        continue

                    elif driver == 'ec2' and 'aws' in handled_drivers and \
                            'aws' in matches[handled_drivers['aws']] and \
                            vm_name in matches[handled_drivers['aws']]['aws']:
                        continue
                    elif driver == 'aws' and 'ec2' in handled_drivers and \
                            'ec2' in matches[handled_drivers['ec2']] and \
                            vm_name in matches[handled_drivers['ec2']]['ec2']:
                        continue

                    if alias not in matches:
                        matches[alias] = {}
                    if driver not in matches[alias]:
                        matches[alias][driver] = {}
                    matches[alias][driver][vm_name] = details

        return matches

    def location_list(self, lookup='all'):
        '''
        Return a mapping of all location data for available providers
        '''
        data = {}

        lookups = self.lookup_providers(lookup)
        if not lookups:
            return data

        for alias, driver in lookups:
            fun = '{0}.avail_locations'.format(driver)
            if fun not in self.clouds:
                # The capability to gather locations is not supported by this
                # cloud module
                log.debug(
                    'The {0!r} cloud driver defined under {1!r} provider '
                    'alias is unable to get the locations information'.format(
                        driver, alias
                    )
                )
                continue

            if alias not in data:
                data[alias] = {}

            try:
                with CloudProviderContext(self.clouds[fun], alias, driver):
                    data[alias][driver] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
        return data

    def image_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        data = {}

        lookups = self.lookup_providers(lookup)
        if not lookups:
            return data

        for alias, driver in lookups:
            fun = '{0}.avail_images'.format(driver)
            if fun not in self.clouds:
                # The capability to gather images is not supported by this
                # cloud module
                log.debug(
                    'The {0!r} cloud driver defined under {1!r} provider '
                    'alias is unable to get the images information'.format(
                        driver,
                        alias
                    )
                )
                continue

            if alias not in data:
                data[alias] = {}

            try:
                with CloudProviderContext(self.clouds[fun], alias, driver):
                    data[alias][driver] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
        return data

    def size_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        data = {}

        lookups = self.lookup_providers(lookup)
        if not lookups:
            return data

        for alias, driver in lookups:
            fun = '{0}.avail_sizes'.format(driver)
            if fun not in self.clouds:
                # The capability to gather sizes is not supported by this
                # cloud module
                log.debug(
                    'The {0!r} cloud driver defined under {1!r} provider '
                    'alias is unable to get the sizes information'.format(
                        driver,
                        alias
                    )
                )
                continue

            if alias not in data:
                data[alias] = {}

            try:
                with CloudProviderContext(self.clouds[fun], alias, driver):
                    data[alias][driver] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info=log.isEnabledFor(logging.DEBUG)
                )
        return data

    def provider_list(self, lookup='all'):
        '''
        Return a mapping of all image data for available providers
        '''
        data = {}
        lookups = self.lookup_providers(lookup)
        if not lookups:
            return data

        for alias, driver in lookups:
            if alias not in data:
                data[alias] = {}
            if driver not in data[alias]:
                data[alias][driver] = {}
        return data

    def create_all(self):
        '''
        Create/Verify the VMs in the VM data
        '''
        ret = []

        for vm_name, vm_details in self.opts['profiles'].iteritems():
            ret.append(
                {vm_name: self.create(vm_details)}
            )

        return ret

    def destroy(self, names, cached=False):
        '''
        Destroy the named VMs
        '''
        processed = {}
        names = set(names)
        matching = self.get_running_by_names(names, cached=cached)
        vms_to_destroy = set()
        for alias, drivers in matching.iteritems():
            for driver, vms in drivers.iteritems():
                for name in vms:
                    if name in names:
                        vms_to_destroy.add((alias, driver, name))

        for alias, driver, name in vms_to_destroy:
            fun = '{0}.destroy'.format(driver)
            with CloudProviderContext(self.clouds[fun], alias, driver):
                ret = self.clouds[fun](name)
            if alias not in processed:
                processed[alias] = {}
            if driver not in processed[alias]:
                processed[alias][driver] = {}
            processed[alias][driver][name] = ret
            names.remove(name)

            if not ret:
                continue

            key_file = os.path.join(
                self.opts['pki_dir'], 'minions', name
            )
            globbed_key_file = glob.glob('{0}.*'.format(key_file))

            if not os.path.isfile(key_file) and not globbed_key_file:
                # There's no such key file!? It might have been renamed
                if isinstance(ret, dict) and 'newname' in ret:
                    saltcloud.utils.remove_key(
                        self.opts['pki_dir'], ret['newname']
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

        if names and not processed:
            # These machines were asked to be destroyed but could not be found
            raise SaltCloudSystemExit(
                'The following VM\'s were not found: {0}'.format(
                    ', '.join(names)
                )
            )

        elif names and processed:
            processed['Not Found'] = names

        elif not processed:
            raise SaltCloudSystemExit('No machines were destroyed!')

        return processed

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

        alias, driver = vm_['provider'].split(':')
        fun = '{0}.create'.format(driver)
        if fun not in self.clouds:
            log.error(
                'Creating {0[name]!r} using {0[provider]!r} as the provider '
                'cannot complete since {1!r} is not available'.format(
                    vm_,
                    driver
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
            alias, driver = vm_['provider'].split(':')
            func = '{0}.create'.format(driver)
            with CloudProviderContext(self.clouds[func], alias, driver):
                output = self.clouds[func](vm_)
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
        # If it's a map then we need to respect the 'requires'
        # so we do it later
        try:
            opt_map = self.opts['map']
        except KeyError:
            opt_map = False
        if self.opts['parallel'] and self.opts['start_action'] and not opt_map:
            log.info(
                'Running {0} on {1}'.format(
                    self.opts['start_action'], vm_['name']
                )
            )
            client = salt.client.LocalClient()
            action_out = client.cmd(
                vm_['name'],
                self.opts['start_action'],
                timeout=self.opts['timeout'] * 60
            )
            output['ret'] = action_out
        return output

    def run_profile(self, profile, names):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        if profile not in self.opts['profiles']:
            msg = 'Profile {0} is not defined'.format(profile)
            log.error(msg)
            return {'Error': msg}

        ret = {}
        profile_details = self.opts['profiles'][profile]
        alias, driver = profile_details['provider'].split(':')
        mapped_providers = self.map_providers_parallel()
        alias_data = mapped_providers.setdefault(alias, {})
        vms = alias_data.setdefault(driver, {})

        for name in names:
            if name in vms and vms[name]['state'].lower() != 'terminated':
                msg = '{0} already exists under {0}:{1}'.format(
                    name, alias, driver
                )
                log.error(msg)
                ret[name] = {'Error': msg}
                continue

            vm_ = profile_details.copy()
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
                # No need to use CloudProviderContext here because self.create
                # takes care of that
                ret[name] = self.create(vm_)
                if not ret[name]:
                    ret[name] = {'Error': 'Failed to deploy VM'}
                    if len(names) == 1:
                        raise SaltCloudSystemExit('Failed to deploy VM')
                    continue
                if self.opts.get('show_deploy_args', False) is False:
                    ret[name].pop('deploy_kwargs', None)
            except (SaltCloudSystemExit, SaltCloudConfigError), exc:
                if len(names) == 1:
                    raise
                ret[name] = {'Error': exc.message}

        return ret

    def do_action(self, names, kwargs):
        '''
        Perform an action on a VM which may be specific to this cloud provider
        '''
        ret = {}
        names = set(names)

        for alias, drivers in self.map_providers_parallel().iteritems():
            if not names:
                break
            for driver, vms in drivers.iteritems():
                if not names:
                    break
                fun = '{0}.{1}'.format(driver, self.opts['action'])
                if fun not in self.clouds:
                    log.info(
                        '\'{0}()\' is not available. Not actioning...'.format(
                            fun
                        )
                    )
                    continue
                for vm_name, vm_details in vms.iteritems():
                    if not names:
                        break
                    if vm_name not in names:
                        continue
                    with CloudProviderContext(self.clouds[fun], alias, driver):
                        if alias not in ret:
                            ret[alias] = {}
                        if driver not in ret[alias]:
                            ret[alias][driver] = {}

                        if kwargs:
                            ret[alias][driver][vm_name] = self.clouds[fun](
                                vm_name, kwargs, call='action'
                            )
                        else:
                            ret[alias][driver][vm_name] = self.clouds[fun](
                                vm_name, call='action'
                            )
                        names.remove(vm_name)

        if not names:
            return ret

        ret['Not Actioned/Not Running'] = list(names)
        return ret

    def do_function(self, prov, func, kwargs):
        '''
        Perform a function against a cloud provider
        '''
        matches = self.lookup_providers(prov)
        if len(matches) > 1:
            raise SaltCloudSystemExit(
                'More than one results matched {0!r}. Please specify '
                'one of: {1}'.format(
                    prov,
                    ', '.join([
                        '{0}:{1}'.format(alias, driver) for
                        (alias, driver) in matches
                    ])
                )
            )

        alias, driver = matches.pop()
        fun = '{0}.{1}'.format(driver, func)
        if fun not in self.clouds:
            raise SaltCloudSystemExit(
                'The {0!r} cloud provider alias, for the {1!r} driver, does '
                'not define the function {2!r}'.format(alias, driver, func)
            )

        log.debug(
            'Trying to execute {0!r} with the following kwargs: {1}'.format(
                fun, kwargs
            )
        )

        with CloudProviderContext(self.clouds[fun], alias, driver):
            if kwargs:
                return {
                    alias: {
                        driver: self.clouds[fun](
                            call='function', kwargs=kwargs
                        )
                    }
                }
            return {
                alias: {
                    driver: self.clouds[fun](call='function')
                }
            }

    def __switch_credentials(self):
        user = self.opts.get('user', None)
        if user is not None and check_user(user) is not True:
            raise SaltCloudSystemExit(
                'salt-cloud needs to run as the same user as salt-master, '
                '{0!r}, but was unable to switch credentials. Please run '
                'salt-cloud as root or as {0!r}'.format(user)
            )

    def __filter_non_working_providers(self):
        '''
        Remove any mis-configured cloud providers from the available listing
        '''
        for alias, drivers in self.opts['providers'].copy().iteritems():
            for driver in drivers.copy().keys():
                fun = '{0}.get_configured_provider'.format(driver)
                if fun not in self.clouds:
                    # Mis-configured provider that got removed?
                    log.warn(
                        'The cloud driver, {0!r}, configured under the '
                        '{1!r} cloud provider alias was not loaded since '
                        '\'{2}()\' could not be found. Removing it from '
                        'the available providers list'.format(
                            driver, alias, fun
                        )
                    )
                    self.opts['providers'][alias].pop(driver)

                    if alias not in self.opts['providers']:
                        continue

                    if not self.opts['providers'][alias]:
                        self.opts['providers'].pop(alias)
                    continue

                with CloudProviderContext(self.clouds[fun], alias, driver):
                    if self.clouds[fun]() is False:
                        log.warn(
                            'The cloud driver, {0!r}, configured under the '
                            '{1!r} cloud provider alias is not properly '
                            'configured. Removing it from the available '
                            'providers list'.format(driver, alias)
                        )
                        self.opts['providers'][alias].pop(driver)

            if alias not in self.opts['providers']:
                continue

            if not self.opts['providers'][alias]:
                self.opts['providers'].pop(alias)


class Map(Cloud):
    '''
    Create a VM stateful map execution object
    '''
    def __init__(self, opts):
        Cloud.__init__(self, opts)
        self.rendered_map = self.read()

    def interpolated_map(self, query='list_nodes', cached=False):
        rendered_map = self.read().copy()
        interpolated_map = {}

        for profile, mapped_vms in rendered_map.items():
            names = set(mapped_vms.keys())
            if profile not in self.opts['profiles']:
                if 'Errors' not in interpolated_map:
                    interpolated_map['Errors'] = {}
                msg = (
                    'No provider for the mapped {0!r} profile was found. '
                    'Skipped VMS: {1}'.format(
                        profile, ', '.join(names)
                    )
                )
                log.info(msg)
                interpolated_map['Errors'][profile] = msg
                continue

            matching = self.get_running_by_names(names, query, cached)
            for alias, drivers in matching.iteritems():
                for driver, vms in drivers.iteritems():
                    for vm_name, vm_details in vms.iteritems():
                        if alias not in interpolated_map:
                            interpolated_map[alias] = {}
                        if driver not in interpolated_map[alias]:
                            interpolated_map[alias][driver] = {}
                        interpolated_map[alias][driver][vm_name] = vm_details
                        names.remove(vm_name)

            if not names:
                continue

            profile_details = self.opts['profiles'][profile]
            alias, driver = profile_details['provider'].split(':')
            for vm_name in names:
                if alias not in interpolated_map:
                    interpolated_map[alias] = {}
                if driver not in interpolated_map[alias]:
                    interpolated_map[alias][driver] = {}
                interpolated_map[alias][driver][vm_name] = 'Absent'

        return interpolated_map

    def delete_map(self, query=None):
        query_map = self.interpolated_map(query=query)
        for alias, drivers in query_map.copy().iteritems():
            for driver, vms in drivers.copy().iteritems():
                for vm_name, vm_details in vms.copy().iteritems():
                    if vm_details == 'Absent':
                        query_map[alias][driver].pop(vm_name)
                    elif vm_details['state'].lower() != 'running':
                        query_map[alias][driver].pop(vm_name)
                if not query_map[alias][driver]:
                    query_map[alias].pop(driver)
            if not query_map[alias]:
                query_map.pop(alias)
        return query_map

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
            map_ = salt.config.include_config(
                map_, self.opts['map'], verbose=False
            )

        # Create expected data format if needed
        for profile, mapped in map_.copy().items():
            if isinstance(mapped, (list, tuple)):
                entries = {}
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
                        entries[name] = overrides
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
                entries = {}
                for name, overrides in mapped.iteritems():
                    overrides.setdefault('name', name)
                    entries[name] = overrides
                map_[profile] = entries
                continue

            if isinstance(mapped, basestring):
                # If it's a single string entry, let's make iterable because of
                # the next step
                mapped = [mapped]

            map_[profile] = {}
            for name in mapped:
                map_[profile][name] = {'name': name}
        return map_

    def _has_loop(self, dmap, seen=None, val=None):
        if seen is None:
            for values in dmap['create'].values():
                seen = []
                try:
                    machines = values['requires']
                except KeyError:
                    machines = []
                for machine in machines:
                    if self._has_loop(dmap, seen=list(seen), val=machine):
                        return True
        else:
            if val in seen:
                return True

            seen.append(val)
            try:
                machines = dmap['create'][val]['requires']
            except KeyError:
                machines = []

            for machine in machines:
                if self._has_loop(dmap, seen=list(seen), val=machine):
                    return True
        return False

    def _calcdep(self, dmap, machine, data, level):
        try:
            deplist = data['requires']
        except KeyError:
            return level
        levels = []
        for name in deplist:
            try:
                data = dmap['create'][name]
            except KeyError:
                try:
                    data = dmap['existing'][name]
                except KeyError:
                    msg = 'Missing dependency in cloud map'
                    log.error(msg)
                    raise SaltCloudException(msg)
            levels.append(self._calcdep(dmap, name, data, level))
        level = max(levels) + 1
        return level

    def map_data(self, cached=False):
        '''
        Create a data map of what to execute on
        '''
        ret = {'create': {}}
        pmap = self.map_providers_parallel(cached=cached)
        exist = set()
        defined = set()
        for profile_name, nodes in self.rendered_map.iteritems():
            if profile_name not in self.opts['profiles']:
                msg = (
                    'The required profile, {0!r}, defined in the map '
                    'does not exist. The defined nodes, {1}, will not '
                    'be created.'.format(
                        profile_name,
                        ', '.join('{0!r}'.format(node) for node in nodes)
                    )
                )
                log.error(msg)
                if 'errors' not in ret:
                    ret['errors'] = {}
                ret['errors'][profile_name] = msg
                continue

            profile_data = self.opts['profiles'].get(profile_name)
            for nodename, overrides in nodes.iteritems():
                # Get the VM name
                nodedata = copy.deepcopy(profile_data)
                # Update profile data with the map overrides
                for setting in ('grains', 'master', 'minion', 'volumes',
                                'requires'):
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

                # merge minion grains from map file
                if 'minion' in overrides:
                    if 'grains' in overrides['minion']:
                        if 'grains' in nodedata['minion']:
                            nodedata['minion']['grains'].update(
                                overrides['minion']['grains']
                            )
                            del(overrides['minion']['grains'])
                            # remove minion key if now is empty dict
                            if len(overrides['minion']) == 0:
                                del(overrides['minion'])

                nodedata.update(overrides)
                # Add the computed information to the return data
                ret['create'][nodename] = nodedata
                # Add the node name to the defined set
                alias, driver = nodedata['provider'].split(':')
                defined.add((alias, driver, nodename))

        def get_matching_by_name(name):
            matches = {}
            for alias, drivers in pmap.iteritems():
                for driver, vms in drivers.iteritems():
                    for vm_name, details in vms.iteritems():
                        if vm_name == name:
                            if driver not in matches:
                                matches[driver] = details['state']
            return matches

        for alias, drivers in pmap.iteritems():
            for driver, vms in drivers.iteritems():
                for name, details in vms.iteritems():
                    exist.add((alias, driver, name))
                    if name not in ret['create']:
                        continue

                    # The machine is set to be created. Does it already exist?
                    matching = get_matching_by_name(name)
                    if not matching:
                        continue

                    # A machine by the same name exists
                    for mdriver, state in matching.iteritems():
                        if name not in ret['create']:
                            # Machine already removed
                            break

                        if mdriver not in ('aws', 'ec2') and \
                                state.lower() != 'terminated':
                            # Regarding other providers, simply remove
                            # them for the create map.
                            log.warn(
                                '{0!r} already exists, removing from '
                                'the create map'.format(name)
                            )
                            if 'existing' not in ret:
                                ret['existing'] = {}
                            ret['existing'][name] = ret['create'].pop(name)
                            continue

                        if state.lower() != 'terminated':
                            log.info(
                                '{0!r} already exists, removing '
                                'from the create map'.format(name)
                            )
                            if 'existing' not in ret:
                                ret['existing'] = {}
                            ret['existing'][name] = ret['create'].pop(name)

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
        if self._has_loop(dmap):
            msg = 'Uh-oh, that cloud map has a dependency loop!'
            log.error(msg)
            raise SaltCloudException(msg)
        #Go through the create list and calc dependencies
        for key, val in dmap['create'].items():
            log.info('Calculating dependencies for {0}'.format(key))
            level = 0
            level = self._calcdep(dmap, key, val, level)
            log.debug('Got execution order {0} for {1}'.format(level, key))
            dmap['create'][key]['level'] = level

        try:
            existing_list = dmap['existing'].items()
        except KeyError:
            existing_list = {}

        for key, val in existing_list:
            log.info('Calculating dependencies for {0}'.format(key))
            level = 0
            level = self._calcdep(dmap, key, val, level)
            log.debug('Got execution order {0} for {1}'.format(level, key))
            dmap['existing'][key]['level'] = level

        #Now sort the create list based on dependencies
        create_list = sorted(dmap['create'].items(),
                             key=lambda x: x[1]['level'])
        output = {}
        if self.opts['parallel']:
            parallel_data = []
        master_name = None
        master_host = None
        master_finger = None
        try:
            master_name, master_profile = (
                (name, profile) for name, profile in create_list
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
            for name, profile in create_list:
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

            elif 'Errors' in out:
                raise SaltCloudSystemExit(
                    'An error occurred while creating the master, not '
                    'continuing: {0}'.format(out['Errors'])
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

        for name, profile in create_list:
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
            # We have deployed in parallel, now do start action in
            # correct order based on dependencies.
            if self.opts['start_action']:
                actionlist = []
                grp = -1
                for key, val in groupby(dmap['create'].values(),
                                        lambda x: x['level']):
                    actionlist.append([])
                    grp += 1
                    for item in val:
                        actionlist[grp].append(item['name'])

                out = {}
                for group in actionlist:
                    log.info(
                        'Running {0} on {1}'.format(
                            self.opts['start_action'], ', '.join(group)
                        )
                    )
                    client = salt.client.LocalClient()
                    out.update(client.cmd(
                        ','.join(group), self.opts['start_action'],
                        timeout=self.opts['timeout'] * 60, expr_form='list'
                    ))
                for obj in output_multip:
                    obj.values()[0]['ret'] = out[obj.keys()[0]]
                    output.update(obj)
            else:
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
            # Show the traceback if the debug logging level is enabled
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
        with CloudProviderContext(cloud.clouds[data['fun']],
                                  data['alias'],
                                  data['driver']):
            return (
                data['alias'],
                data['driver'],
                saltcloud.utils.simple_types_filter(
                    cloud.clouds[data['fun']]()
                )
            )
    except Exception as err:
        log.debug(
            'Failed to execute \'{0}()\' while querying for running '
            'nodes: {1}'.format(data['fun'], err),
            # Show the traceback if the debug logging level is
            # enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        # Failed to communicate with the provider, don't list any nodes
        return (data['alias'], data['driver'], ())
