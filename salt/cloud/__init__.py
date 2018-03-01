# -*- coding: utf-8 -*-
'''
The top level interface used to translate configuration data back to the
correct cloud modules
'''

# Import python libs
from __future__ import absolute_import, print_function, generators, unicode_literals
import os
import copy
import glob
import time
import signal
import logging
import traceback
import multiprocessing
import sys
from itertools import groupby

# Import salt.cloud libs
from salt.exceptions import (
    SaltCloudNotFound,
    SaltCloudException,
    SaltCloudSystemExit,
    SaltCloudConfigError
)

# Import salt libs
import salt.config
import salt.client
import salt.loader
import salt.utils.args
import salt.utils.cloud
import salt.utils.context
import salt.utils.crypt
import salt.utils.data
import salt.utils.dictupdate
import salt.utils.files
import salt.utils.verify
import salt.utils.yaml
import salt.utils.user
import salt.syspaths
from salt.template import compile_template

# Import third party libs
try:
    import Cryptodome.Random
except ImportError:
    try:
        import Crypto.Random
    except ImportError:
        pass  # pycrypto < 2.1
from salt.ext import six
from salt.ext.six.moves import input  # pylint: disable=import-error,redefined-builtin

# Get logging started
log = logging.getLogger(__name__)


def communicator(func):
    '''Warning, this is a picklable decorator !'''
    def _call(queue, args, kwargs):
        '''called with [queue, args, kwargs] as first optional arg'''
        kwargs['queue'] = queue
        ret = None
        try:
            ret = func(*args, **kwargs)
            queue.put('END')
        except KeyboardInterrupt as ex:
            trace = traceback.format_exc()
            queue.put('KEYBOARDINT')
            queue.put('Keyboard interrupt')
            queue.put('{0}\n{1}\n'.format(ex, trace))
        except Exception as ex:
            trace = traceback.format_exc()
            queue.put('ERROR')
            queue.put('Exception')
            queue.put('{0}\n{1}\n'.format(ex, trace))
        return ret
    return _call


def enter_mainloop(target,
                   mapped_args=None,
                   args=None,
                   kwargs=None,
                   pool=None,
                   pool_size=None,
                   callback=None,
                   queue=None):
    '''
    Manage a multiprocessing pool

    - If the queue does not output anything, the pool runs indefinitely

    - If the queue returns KEYBOARDINT or ERROR, this will kill the pool
      totally calling terminate & join and ands with a SaltCloudSystemExit
      exception notifying callers from the abnormal termination

    - If the queue returns END or callback is defined and returns True,
      it just join the process and return the data.

    target
        the function you want to execute in multiproccessing
    pool
        pool object can be None if you want a default pool, but you ll
        have then to define pool_size instead
    pool_size
        pool size if you did not provide yourself a pool
    callback
        a boolean taking a string in argument which returns True to
        signal that 'target' is finished and we need to join
        the pool
    queue
        A custom multiproccessing queue in case you want to do
        extra stuff and need it later in your program
    args
        positional arguments to call the function with
        if you don't want to use pool.map

    mapped_args
        a list of one or more arguments combinations to call the function with
        e.g. (foo, [[1], [2]]) will call::

                foo([1])
                foo([2])

    kwargs
        kwargs to give to the function in case of process

    Attention, the function must have the following signature:

            target(queue, *args, **kw)

    You may use the 'communicator' decorator to generate such a function
    (see end of this file)
    '''
    if not kwargs:
        kwargs = {}
    if not pool_size:
        pool_size = 1
    if not pool:
        pool = multiprocessing.Pool(pool_size)
    if not queue:
        manager = multiprocessing.Manager()
        queue = manager.Queue()

    if mapped_args is not None and not mapped_args:
        msg = (
            'We are called to asynchronously execute {0}'
            ' but we do no have anything to execute, weird,'
            ' we bail out'.format(target))
        log.error(msg)
        raise SaltCloudSystemExit('Exception caught\n{0}'.format(msg))
    elif mapped_args is not None:
        iterable = [[queue, [arg], kwargs] for arg in mapped_args]
        ret = pool.map(func=target, iterable=iterable)
    else:
        ret = pool.apply(target, [queue, args, kwargs])
    while True:
        test = queue.get()
        if test in ['ERROR', 'KEYBOARDINT']:
            type_ = queue.get()
            trace = queue.get()
            msg = 'Caught {0}, terminating workers\n'.format(type_)
            msg += 'TRACE: {0}\n'.format(trace)
            log.error(msg)
            pool.terminate()
            pool.join()
            raise SaltCloudSystemExit('Exception caught\n{0}'.format(msg))
        elif test in ['END'] or (callback and callback(test)):
            pool.close()
            pool.join()
            break
        else:
            time.sleep(0.125)
    return ret


class CloudClient(object):
    '''
    The client class to wrap cloud interactions
    '''
    def __init__(self, path=None, opts=None, config_dir=None, pillars=None):
        if opts:
            self.opts = opts
        else:
            self.opts = salt.config.cloud_config(path)

        # Check the cache-dir exists. If not, create it.
        v_dirs = [self.opts['cachedir']]
        salt.utils.verify.verify_env(v_dirs, salt.utils.user.get_user())

        if pillars:
            for name, provider in six.iteritems(pillars.pop('providers', {})):
                driver = provider['driver']
                provider['profiles'] = {}
                self.opts['providers'].update({name: {driver: provider}})
            for name, profile in six.iteritems(pillars.pop('profiles', {})):
                provider = profile['provider'].split(':')[0]
                driver = next(six.iterkeys(self.opts['providers'][provider]))
                profile['provider'] = '{0}:{1}'.format(provider, driver)
                profile['profile'] = name
                self.opts['profiles'].update({name: profile})
                self.opts['providers'][provider][driver]['profiles'].update({name: profile})
            self.opts.update(pillars)

    def _opts_defaults(self, **kwargs):
        '''
        Set the opts dict to defaults and allow for opts to be overridden in
        the kwargs
        '''
        # Let's start with the default salt cloud configuration
        opts = salt.config.DEFAULT_CLOUD_OPTS.copy()
        # Update it with the loaded configuration
        opts.update(self.opts.copy())
        # Reset some of the settings to sane values
        opts['parallel'] = False
        opts['keep_tmp'] = False
        opts['deploy'] = True
        opts['update_bootstrap'] = False
        opts['show_deploy_args'] = False
        opts['script_args'] = ''
        # Update it with the passed kwargs
        if 'kwargs' in kwargs:
            opts.update(kwargs['kwargs'])
        opts.update(kwargs)
        profile = opts.get('profile', None)
        # filter other profiles if one is specified
        if profile:
            tmp_profiles = opts.get('profiles', {}).copy()
            for _profile in [a for a in tmp_profiles]:
                if not _profile == profile:
                    tmp_profiles.pop(_profile)
            # if profile is specified and we have enough info about providers
            # also filter them to speedup methods like
            # __filter_non_working_providers
            providers = [a.get('provider', '').split(':')[0]
                         for a in six.itervalues(tmp_profiles)
                         if a.get('provider', '')]
            if providers:
                _providers = opts.get('providers', {})
                for provider in _providers.copy():
                    if provider not in providers:
                        _providers.pop(provider)
        return opts

    def low(self, fun, low):
        '''
        Pass the cloud function and low data structure to run
        '''
        l_fun = getattr(self, fun)
        f_call = salt.utils.args.format_call(l_fun, low)
        return l_fun(*f_call.get('args', ()), **f_call.get('kwargs', {}))

    def list_sizes(self, provider=None):
        '''
        List all available sizes in configured cloud systems
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        return salt.utils.data.simple_types_filter(
            mapper.size_list(provider)
        )

    def list_images(self, provider=None):
        '''
        List all available images in configured cloud systems
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        return salt.utils.data.simple_types_filter(
            mapper.image_list(provider)
        )

    def list_locations(self, provider=None):
        '''
        List all available locations in configured cloud systems
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        return salt.utils.data.simple_types_filter(
            mapper.location_list(provider)
        )

    def query(self, query_type='list_nodes'):
        '''
        Query basic instance information
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        mapper.opts['selected_query_option'] = 'list_nodes'
        return mapper.map_providers_parallel(query_type)

    def full_query(self, query_type='list_nodes_full'):
        '''
        Query all instance information
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        mapper.opts['selected_query_option'] = 'list_nodes_full'
        return mapper.map_providers_parallel(query_type)

    def select_query(self, query_type='list_nodes_select'):
        '''
        Query select instance information
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        mapper.opts['selected_query_option'] = 'list_nodes_select'
        return mapper.map_providers_parallel(query_type)

    def min_query(self, query_type='list_nodes_min'):
        '''
        Query select instance information
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        mapper.opts['selected_query_option'] = 'list_nodes_min'
        return mapper.map_providers_parallel(query_type)

    def profile(self, profile, names, vm_overrides=None, **kwargs):
        '''
        Pass in a profile to create, names is a list of vm names to allocate

            vm_overrides is a special dict that will be per node options
            overrides

        Example:

        .. code-block:: python

            >>> client= salt.cloud.CloudClient(path='/etc/salt/cloud')
            >>> client.profile('do_512_git', names=['minion01',])
            {'minion01': {'backups_active': 'False',
                    'created_at': '2014-09-04T18:10:15Z',
                    'droplet': {'event_id': 31000502,
                                 'id': 2530006,
                                 'image_id': 5140006,
                                 'name': 'minion01',
                                 'size_id': 66},
                    'id': '2530006',
                    'image_id': '5140006',
                    'ip_address': '107.XXX.XXX.XXX',
                    'locked': 'True',
                    'name': 'minion01',
                    'private_ip_address': None,
                    'region_id': '4',
                    'size_id': '66',
                    'status': 'new'}}


        '''
        if not vm_overrides:
            vm_overrides = {}
        kwargs['profile'] = profile
        mapper = salt.cloud.Map(self._opts_defaults(**kwargs))
        if isinstance(names, six.string_types):
            names = names.split(',')
        return salt.utils.data.simple_types_filter(
            mapper.run_profile(profile, names, vm_overrides=vm_overrides)
        )

    def map_run(self, path=None, **kwargs):
        '''
        Pass in a location for a map to execute
        '''
        kwarg = {}
        if path:
            kwarg['map'] = path
        kwarg.update(kwargs)
        mapper = salt.cloud.Map(self._opts_defaults(**kwarg))
        dmap = mapper.map_data()
        return salt.utils.data.simple_types_filter(
            mapper.run_map(dmap)
        )

    def destroy(self, names):
        '''
        Destroy the named VMs
        '''
        mapper = salt.cloud.Map(self._opts_defaults(destroy=True))
        if isinstance(names, six.string_types):
            names = names.split(',')
        return salt.utils.data.simple_types_filter(
            mapper.destroy(names)
        )

    def create(self, provider, names, **kwargs):
        '''
        Create the named VMs, without using a profile

        Example:

        .. code-block:: python

            client.create(provider='my-ec2-config', names=['myinstance'],
                image='ami-1624987f', size='t1.micro', ssh_username='ec2-user',
                securitygroup='default', delvol_on_destroy=True)
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        providers = self.opts['providers']
        if provider in providers:
            provider += ':{0}'.format(next(six.iterkeys(providers[provider])))
        else:
            return False
        if isinstance(names, six.string_types):
            names = names.split(',')
        ret = {}
        for name in names:
            vm_ = kwargs.copy()
            vm_['name'] = name
            vm_['driver'] = provider

            # This function doesn't require a profile, but many cloud drivers
            # check for profile information (which includes the provider key) to
            # help with config file debugging and setting up instances. Setting
            # the profile and provider defaults here avoids errors in other
            # cloud functions relying on these keys. See SaltStack Issue #41971
            # and PR #38166 for more information.
            vm_['profile'] = None
            vm_['provider'] = provider

            ret[name] = salt.utils.data.simple_types_filter(
                mapper.create(vm_))
        return ret

    def extra_action(self, names, provider, action, **kwargs):
        '''
        Perform actions with block storage devices

        Example:

        .. code-block:: python

            client.extra_action(names=['myblock'], action='volume_create',
                provider='my-nova', kwargs={'voltype': 'SSD', 'size': 1000}
            )
            client.extra_action(names=['salt-net'], action='network_create',
                provider='my-nova', kwargs={'cidr': '192.168.100.0/24'}
            )
        '''
        mapper = salt.cloud.Map(self._opts_defaults())
        providers = mapper.map_providers_parallel()
        if provider in providers:
            provider += ':{0}'.format(next(six.iterkeys(providers[provider])))
        else:
            return False
        if isinstance(names, six.string_types):
            names = names.split(',')

        ret = {}
        for name in names:
            extra_ = kwargs.copy()
            extra_['name'] = name
            extra_['provider'] = provider
            extra_['profile'] = None
            extra_['action'] = action
            ret[name] = salt.utils.data.simple_types_filter(
                mapper.extras(extra_)
            )
        return ret

    def action(
        self,
        fun=None,
        cloudmap=None,
        names=None,
        provider=None,
        instance=None,
        kwargs=None
    ):
        '''
        Execute a single action via the cloud plugin backend

        Examples:

        .. code-block:: python

            client.action(fun='show_instance', names=['myinstance'])
            client.action(fun='show_image', provider='my-ec2-config',
                kwargs={'image': 'ami-10314d79'}
            )
        '''
        if kwargs is None:
            kwargs = {}

        mapper = salt.cloud.Map(self._opts_defaults(
            action=fun,
            names=names,
            **kwargs))
        if instance:
            if names:
                raise SaltCloudConfigError(
                    'Please specify either a list of \'names\' or a single '
                    '\'instance\', but not both.'
                )
            names = [instance]

        if names and not provider:
            self.opts['action'] = fun
            return mapper.do_action(names, kwargs)

        if provider and not names:
            return mapper.do_function(provider, fun, kwargs)
        else:
            # This should not be called without either an instance or a
            # provider. If both an instance/list of names and a provider
            # are given, then we also need to exit. We can only have one
            # or the other.
            raise SaltCloudConfigError(
                'Either an instance (or list of names) or a provider must be '
                'specified, but not both.'
            )


class Cloud(object):
    '''
    An object for the creation of new VMs
    '''
    def __init__(self, opts):
        self.opts = opts
        self.clouds = salt.loader.clouds(self.opts)
        self.__filter_non_working_providers()
        self.__cached_provider_queries = {}

    def get_configured_providers(self):
        '''
        Return the configured providers
        '''
        providers = set()
        for alias, drivers in six.iteritems(self.opts['providers']):
            if len(drivers) > 1:
                for driver in drivers:
                    providers.add('{0}:{1}'.format(alias, driver))
                continue
            providers.add(alias)
        return providers

    def lookup_providers(self, lookup):
        '''
        Get a dict describing the configured providers
        '''
        if lookup is None:
            lookup = 'all'
        if lookup == 'all':
            providers = set()
            for alias, drivers in six.iteritems(self.opts['providers']):
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
                    'No cloud providers matched \'{0}\'. Available: {1}'.format(
                        lookup, ', '.join(self.get_configured_providers())
                    )
                )

        providers = set()
        for alias, drivers in six.iteritems(self.opts['providers']):
            for driver in drivers:
                if lookup in (alias, driver):
                    providers.add((alias, driver))

        if not providers:
            raise SaltCloudSystemExit(
                'No cloud providers matched \'{0}\'. '
                'Available selections: {1}'.format(
                    lookup, ', '.join(self.get_configured_providers())
                )
            )
        return providers

    def lookup_profiles(self, provider, lookup):
        '''
        Return a dictionary describing the configured profiles
        '''
        if provider is None:
            provider = 'all'
        if lookup is None:
            lookup = 'all'

        if lookup == 'all':
            profiles = set()
            provider_profiles = set()
            for alias, info in six.iteritems(self.opts['profiles']):
                providers = info.get('provider')

                if providers:
                    given_prov_name = providers.split(':')[0]
                    salt_prov_name = providers.split(':')[1]
                    if given_prov_name == provider:
                        provider_profiles.add((alias, given_prov_name))
                    elif salt_prov_name == provider:
                        provider_profiles.add((alias, salt_prov_name))
                    profiles.add((alias, given_prov_name))

            if not profiles:
                raise SaltCloudSystemExit(
                    'There are no cloud profiles configured.'
                )

            if provider != 'all':
                return provider_profiles

            return profiles

    def map_providers(self, query='list_nodes', cached=False):
        '''
        Return a mapping of what named VMs are running on what VM providers
        based on what providers are defined in the configuration and VMs
        '''
        if cached is True and query in self.__cached_provider_queries:
            return self.__cached_provider_queries[query]

        pmap = {}
        for alias, drivers in six.iteritems(self.opts['providers']):
            for driver, details in six.iteritems(drivers):
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
                    with salt.utils.context.func_globals_inject(
                        self.clouds[fun],
                        __active_provider_name__=':'.join([alias, driver])
                    ):
                        pmap[alias][driver] = self.clouds[fun]()
                except Exception as err:
                    log.debug(
                        'Failed to execute \'{0}()\' while querying for '
                        'running nodes: {1}'.format(fun, err),
                        # Show the traceback if the debug logging level is
                        # enabled
                        exc_info_on_loglevel=logging.DEBUG
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

        # Optimize Providers
        opts['providers'] = self._optimize_providers(opts['providers'])
        for alias, drivers in six.iteritems(opts['providers']):
            # Make temp query for this driver to avoid overwrite next
            this_query = query
            for driver, details in six.iteritems(drivers):
                # If driver has function list_nodes_min, just replace it
                # with query param to check existing vms on this driver
                # for minimum information, Otherwise still use query param.
                if opts.get('selected_query_option') is None and '{0}.list_nodes_min'.format(driver) in self.clouds:
                    this_query = 'list_nodes_min'

                fun = '{0}.{1}'.format(driver, this_query)
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
                    'query': this_query,
                    'alias': alias,
                    'driver': driver
                })
        output = {}
        if not multiprocessing_data:
            return output

        data_count = len(multiprocessing_data)
        pool = multiprocessing.Pool(data_count < 10 and data_count or 10,
                                    init_pool_worker)
        parallel_pmap = enter_mainloop(_run_parallel_map_providers_query,
                                       multiprocessing_data,
                                       pool=pool)
        for alias, driver, details in parallel_pmap:
            if not details:
                # There's no providers details?! Skip it!
                continue
            if alias not in output:
                output[alias] = {}
            output[alias][driver] = details

        self.__cached_provider_queries[query] = output
        return output

    def get_running_by_names(self, names, query='list_nodes', cached=False,
                             profile=None):
        if isinstance(names, six.string_types):
            names = [names]

        matches = {}
        handled_drivers = {}
        mapped_providers = self.map_providers_parallel(query, cached=cached)
        for alias, drivers in six.iteritems(mapped_providers):
            for driver, vms in six.iteritems(drivers):
                if driver not in handled_drivers:
                    handled_drivers[driver] = alias
                # When a profile is specified, only return an instance
                # that matches the provider specified in the profile.
                # This solves the issues when many providers return the
                # same instance. For example there may be one provider for
                # each availability zone in amazon in the same region, but
                # the search returns the same instance for each provider
                # because amazon returns all instances in a region, not
                # availability zone.
                if profile and alias not in self.opts['profiles'][profile]['provider'].split(':')[0]:
                    continue

                for vm_name, details in six.iteritems(vms):
                    # XXX: The logic below can be removed once the aws driver
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

    def _optimize_providers(self, providers):
        '''
        Return an optimized mapping of available providers
        '''
        new_providers = {}
        provider_by_driver = {}

        for alias, driver in six.iteritems(providers):
            for name, data in six.iteritems(driver):
                if name not in provider_by_driver:
                    provider_by_driver[name] = {}

                provider_by_driver[name][alias] = data

        for driver, providers_data in six.iteritems(provider_by_driver):
            fun = '{0}.optimize_providers'.format(driver)
            if fun not in self.clouds:
                log.debug(
                    'The \'{0}\' cloud driver is unable to be optimized.'.format(
                        driver
                    )
                )

                for name, prov_data in six.iteritems(providers_data):
                    if name not in new_providers:
                        new_providers[name] = {}
                    new_providers[name][driver] = prov_data
                continue

            new_data = self.clouds[fun](providers_data)
            if new_data:
                for name, prov_data in six.iteritems(new_data):
                    if name not in new_providers:
                        new_providers[name] = {}
                    new_providers[name][driver] = prov_data

        return new_providers

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
                    'The \'{0}\' cloud driver defined under \'{1}\' provider '
                    'alias is unable to get the locations information'.format(
                        driver, alias
                    )
                )
                continue

            if alias not in data:
                data[alias] = {}

            try:

                with salt.utils.context.func_globals_inject(
                    self.clouds[fun],
                    __active_provider_name__=':'.join([alias, driver])
                ):
                    data[alias][driver] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
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
                    'The \'{0}\' cloud driver defined under \'{1}\' provider '
                    'alias is unable to get the images information'.format(
                        driver,
                        alias
                    )
                )
                continue

            if alias not in data:
                data[alias] = {}

            try:
                with salt.utils.context.func_globals_inject(
                    self.clouds[fun],
                    __active_provider_name__=':'.join([alias, driver])
                ):
                    data[alias][driver] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
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
                    'The \'{0}\' cloud driver defined under \'{1}\' provider '
                    'alias is unable to get the sizes information'.format(
                        driver,
                        alias
                    )
                )
                continue

            if alias not in data:
                data[alias] = {}

            try:
                with salt.utils.context.func_globals_inject(
                    self.clouds[fun],
                    __active_provider_name__=':'.join([alias, driver])
                ):
                    data[alias][driver] = self.clouds[fun]()
            except Exception as err:
                log.error(
                    'Failed to get the output of \'{0}()\': {1}'.format(
                        fun, err
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
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

    def profile_list(self, provider, lookup='all'):
        '''
        Return a mapping of all configured profiles
        '''
        data = {}
        lookups = self.lookup_profiles(provider, lookup)

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

        for vm_name, vm_details in six.iteritems(self.opts['profiles']):
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
        parallel_data = []
        for alias, drivers in six.iteritems(matching):
            for driver, vms in six.iteritems(drivers):
                for name in vms:
                    if name in names:
                        vms_to_destroy.add((alias, driver, name))
                        if self.opts['parallel']:
                            parallel_data.append({
                                'opts': self.opts,
                                'name': name,
                                'alias': alias,
                                'driver': driver,
                            })

        # destroying in parallel
        if self.opts['parallel'] and len(parallel_data) > 0:
            # set the pool size based on configuration or default to
            # the number of machines we're destroying
            if 'pool_size' in self.opts:
                pool_size = self.opts['pool_size']
            else:
                pool_size = len(parallel_data)
            log.info('Destroying in parallel mode; '
                     'Cloud pool size: {0}'.format(pool_size))

            # kick off the parallel destroy
            output_multip = enter_mainloop(
                _destroy_multiprocessing, parallel_data, pool_size=pool_size)

            # massage the multiprocessing output a bit
            ret_multip = {}
            for obj in output_multip:
                ret_multip.update(obj)

            # build up a data structure similar to what the non-parallel
            # destroy uses
            for obj in parallel_data:
                alias = obj['alias']
                driver = obj['driver']
                name = obj['name']
                if alias not in processed:
                    processed[alias] = {}
                if driver not in processed[alias]:
                    processed[alias][driver] = {}
                processed[alias][driver][name] = ret_multip[name]
                if name in names:
                    names.remove(name)

        # not destroying in parallel
        else:
            log.info('Destroying in non-parallel mode.')
            for alias, driver, name in vms_to_destroy:
                fun = '{0}.destroy'.format(driver)
                with salt.utils.context.func_globals_inject(
                    self.clouds[fun],
                    __active_provider_name__=':'.join([alias, driver])
                ):
                    ret = self.clouds[fun](name)
                if alias not in processed:
                    processed[alias] = {}
                if driver not in processed[alias]:
                    processed[alias][driver] = {}
                processed[alias][driver][name] = ret
                if name in names:
                    names.remove(name)

        # now the processed data structure contains the output from either
        # the parallel or non-parallel destroy and we should finish up
        # with removing minion keys if necessary
        for alias, driver, name in vms_to_destroy:
            ret = processed[alias][driver][name]
            if not ret:
                continue

            vm_ = {
                'name': name,
                'profile': None,
                'provider': ':'.join([alias, driver]),
                'driver': driver
            }
            minion_dict = salt.config.get_cloud_config_value(
                'minion', vm_, self.opts, default={}
            )
            key_file = os.path.join(
                self.opts['pki_dir'], 'minions', minion_dict.get('id', name)
            )
            globbed_key_file = glob.glob('{0}.*'.format(key_file))

            if not os.path.isfile(key_file) and not globbed_key_file:
                # There's no such key file!? It might have been renamed
                if isinstance(ret, dict) and 'newname' in ret:
                    salt.utils.cloud.remove_key(
                        self.opts['pki_dir'], ret['newname']
                    )
                continue

            if os.path.isfile(key_file) and not globbed_key_file:
                # Single key entry. Remove it!
                salt.utils.cloud.remove_key(self.opts['pki_dir'], os.path.basename(key_file))
                continue

            # Since we have globbed matches, there are probably some keys for which their minion
            # configuration has append_domain set.
            if not os.path.isfile(key_file) and globbed_key_file and len(globbed_key_file) == 1:
                # Single entry, let's remove it!
                salt.utils.cloud.remove_key(
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
                'with \'{0}\'. We need to ask you which one should be '
                'deleted:'.format(
                    name
                )
            )
            while True:
                for idx, filename in enumerate(globbed_key_file):
                    print(' {0}: {1}'.format(
                        idx, os.path.basename(filename)
                    ))
                selection = input(
                    'Which minion key should be deleted(number)? '
                )
                try:
                    selection = int(selection)
                except ValueError:
                    print(
                        '\'{0}\' is not a valid selection.'.format(selection)
                    )

                try:
                    filename = os.path.basename(
                        globbed_key_file.pop(selection)
                    )
                except Exception:
                    continue

                delete = input(
                    'Delete \'{0}\'? [Y/n]? '.format(filename)
                )
                if delete == '' or delete.lower().startswith('y'):
                    salt.utils.cloud.remove_key(
                        self.opts['pki_dir'], filename
                    )
                    print('Deleted \'{0}\''.format(filename))
                    break

                print('Did not delete \'{0}\''.format(filename))
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
        for prov, nodes in six.iteritems(pmap):
            acts[prov] = []
            for node in nodes:
                if node in names:
                    acts[prov].append(node)
        for prov, names_ in six.iteritems(acts):
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

        minion_dict = salt.config.get_cloud_config_value(
            'minion', vm_, self.opts, default={}
        )

        alias, driver = vm_['provider'].split(':')
        fun = '{0}.create'.format(driver)
        if fun not in self.clouds:
            log.error(
                'Creating \'{0[name]}\' using \'{0[provider]}\' as the provider '
                'cannot complete since \'{1}\' is not available'.format(
                    vm_,
                    driver
                )
            )
            return

        deploy = salt.config.get_cloud_config_value('deploy', vm_, self.opts)
        make_master = salt.config.get_cloud_config_value(
            'make_master',
            vm_,
            self.opts
        )

        if deploy:
            if not make_master and 'master' not in minion_dict:
                log.warning(
                    'There\'s no master defined on the \'{0}\' VM settings.'.format(
                        vm_['name']
                    )
                )

            if 'pub_key' not in vm_ and 'priv_key' not in vm_:
                log.debug('Generating minion keys for \'{0[name]}\''.format(vm_))
                priv, pub = salt.utils.cloud.gen_keys(
                    salt.config.get_cloud_config_value(
                        'keysize',
                        vm_,
                        self.opts
                    )
                )
                vm_['pub_key'] = pub
                vm_['priv_key'] = priv
        else:
            # Note(pabelanger): We still reference pub_key and priv_key when
            # deploy is disabled.
            vm_['pub_key'] = None
            vm_['priv_key'] = None

        key_id = minion_dict.get('id', vm_['name'])

        domain = vm_.get('domain')
        if vm_.get('use_fqdn') and domain:
            minion_dict['append_domain'] = domain

        if 'append_domain' in minion_dict:
            key_id = '.'.join([key_id, minion_dict['append_domain']])

        if make_master is True and 'master_pub' not in vm_ and 'master_pem' not in vm_:
            log.debug(
                'Generating the master keys for \'{0[name]}\''.format(
                    vm_
                )
            )
            master_priv, master_pub = salt.utils.cloud.gen_keys(
                salt.config.get_cloud_config_value(
                    'keysize',
                    vm_,
                    self.opts
                )
            )
            vm_['master_pub'] = master_pub
            vm_['master_pem'] = master_priv

        if local_master is True and deploy is True:
            # Accept the key on the local master
            salt.utils.cloud.accept_key(
                self.opts['pki_dir'], vm_['pub_key'], key_id
            )

        vm_['os'] = salt.config.get_cloud_config_value(
            'script',
            vm_,
            self.opts
        )

        try:
            vm_['inline_script'] = salt.config.get_cloud_config_value(
                'inline_script',
                vm_,
                self.opts
            )
        except KeyError:
            pass

        try:
            alias, driver = vm_['provider'].split(':')
            func = '{0}.create'.format(driver)
            with salt.utils.context.func_globals_inject(
                self.clouds[fun],
                __active_provider_name__=':'.join([alias, driver])
            ):
                output = self.clouds[func](vm_)
            if output is not False and 'sync_after_install' in self.opts:
                if self.opts['sync_after_install'] not in (
                        'all', 'modules', 'states', 'grains'):
                    log.error('Bad option for sync_after_install')
                    return output

                # A small pause helps the sync work more reliably
                time.sleep(3)

                start = int(time.time())
                while int(time.time()) < start + 60:
                    # We'll try every <timeout> seconds, up to a minute
                    mopts_ = salt.config.DEFAULT_MINION_OPTS
                    conf_path = '/'.join(self.opts['conf_file'].split('/')[:-1])
                    mopts_.update(
                        salt.config.minion_config(
                            os.path.join(conf_path,
                                         'minion')
                        )
                    )

                    client = salt.client.get_local_client(mopts=self.opts)

                    ret = client.cmd(
                        vm_['name'],
                        'saltutil.sync_{0}'.format(self.opts['sync_after_install']),
                        timeout=self.opts['timeout']
                    )
                    if ret:
                        log.info(
                            six.u('Synchronized the following dynamic modules: '
                                  '  {0}').format(ret)
                        )
                        break
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
            client = salt.client.get_local_client(mopts=self.opts)
            action_out = client.cmd(
                vm_['name'],
                self.opts['start_action'],
                timeout=self.opts['timeout'] * 60
            )
            output['ret'] = action_out
        return output

    def extras(self, extra_):
        '''
        Extra actions
        '''
        output = {}

        alias, driver = extra_['provider'].split(':')
        fun = '{0}.{1}'.format(driver, extra_['action'])
        if fun not in self.clouds:
            log.error(
                'Creating \'{0[name]}\' using \'{0[provider]}\' as the provider '
                'cannot complete since \'{1}\' is not available'.format(
                    extra_,
                    driver
                )
            )
            return

        try:
            with salt.utils.context.func_globals_inject(
                self.clouds[fun],
                __active_provider_name__=extra_['provider']
            ):
                output = self.clouds[fun](**extra_)
        except KeyError as exc:
            log.exception(
                (
                    'Failed to perform {0[provider]}.{0[action]} '
                    'on {0[name]}. '
                    'Configuration value {1} needs to be set'
                ).format(extra_, exc)
            )
        return output

    def run_profile(self, profile, names, vm_overrides=None):
        '''
        Parse over the options passed on the command line and determine how to
        handle them
        '''
        if profile not in self.opts['profiles']:
            msg = 'Profile {0} is not defined'.format(profile)
            log.error(msg)
            return {'Error': msg}

        ret = {}
        if not vm_overrides:
            vm_overrides = {}

        try:
            with salt.utils.files.fopen(self.opts['conf_file'], 'r') as mcc:
                main_cloud_config = salt.utils.yaml.safe_load(mcc)
            if not main_cloud_config:
                main_cloud_config = {}
        except KeyError:
            main_cloud_config = {}
        except IOError:
            main_cloud_config = {}

        if main_cloud_config is None:
            main_cloud_config = {}

        mapped_providers = self.map_providers_parallel()
        profile_details = self.opts['profiles'][profile]
        vms = {}
        for prov, val in six.iteritems(mapped_providers):
            prov_name = next(iter(val))
            for node in mapped_providers[prov][prov_name]:
                vms[node] = mapped_providers[prov][prov_name][node]
                vms[node]['provider'] = prov
                vms[node]['driver'] = prov_name
        alias, driver = profile_details['provider'].split(':')

        provider_details = self.opts['providers'][alias][driver].copy()
        del provider_details['profiles']

        for name in names:
            if name in vms:
                prov = vms[name]['provider']
                driv = vms[name]['driver']
                msg = u'{0} already exists under {1}:{2}'.format(
                    name, prov, driv
                )
                log.error(msg)
                ret[name] = {'Error': msg}
                continue

            vm_ = main_cloud_config.copy()
            vm_.update(provider_details)
            vm_.update(profile_details)
            vm_.update(vm_overrides)

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
                # No need to inject __active_provider_name__ into the context
                # here because self.create takes care of that
                ret[name] = self.create(vm_)
                if not ret[name]:
                    ret[name] = {'Error': 'Failed to deploy VM'}
                    if len(names) == 1:
                        raise SaltCloudSystemExit('Failed to deploy VM')
                    continue
                if self.opts.get('show_deploy_args', False) is False:
                    ret[name].pop('deploy_kwargs', None)
            except (SaltCloudSystemExit, SaltCloudConfigError) as exc:
                if len(names) == 1:
                    raise
                ret[name] = {'Error': str(exc)}

        return ret

    def do_action(self, names, kwargs):
        '''
        Perform an action on a VM which may be specific to this cloud provider
        '''
        ret = {}
        invalid_functions = {}
        names = set(names)

        for alias, drivers in six.iteritems(self.map_providers_parallel()):
            if not names:
                break
            for driver, vms in six.iteritems(drivers):
                if not names:
                    break
                valid_function = True
                fun = '{0}.{1}'.format(driver, self.opts['action'])
                if fun not in self.clouds:
                    log.info(
                        '\'{0}()\' is not available. Not actioning...'.format(
                            fun
                        )
                    )
                    valid_function = False
                for vm_name, vm_details in six.iteritems(vms):
                    if not names:
                        break
                    if vm_name not in names:
                        if not isinstance(vm_details, dict):
                            vm_details = {}
                        if 'id' in vm_details and vm_details['id'] in names:
                            vm_name = vm_details['id']
                        else:
                            log.debug(
                                'vm:{0} in provider:{1} is not in name '
                                'list:\'{2}\''.format(vm_name, driver, names)
                            )
                            continue

                    # Build the dictionary of invalid functions with their associated VMs.
                    if valid_function is False:
                        if invalid_functions.get(fun) is None:
                            invalid_functions.update({fun: []})
                        invalid_functions[fun].append(vm_name)
                        continue

                    with salt.utils.context.func_globals_inject(
                        self.clouds[fun],
                        __active_provider_name__=':'.join([alias, driver])
                    ):
                        if alias not in ret:
                            ret[alias] = {}
                        if driver not in ret[alias]:
                            ret[alias][driver] = {}

                        # Clean kwargs of "__pub_*" data before running the cloud action call.
                        # Prevents calling positional "kwarg" arg before "call" when no kwarg
                        # argument is present in the cloud driver function's arg spec.
                        kwargs = salt.utils.args.clean_kwargs(**kwargs)

                        if kwargs:
                            ret[alias][driver][vm_name] = self.clouds[fun](
                                vm_name, kwargs, call='action'
                            )
                        else:
                            ret[alias][driver][vm_name] = self.clouds[fun](
                                vm_name, call='action'
                            )
                        names.remove(vm_name)

        # Set the return information for the VMs listed in the invalid_functions dict.
        missing_vms = set()
        if invalid_functions:
            ret['Invalid Actions'] = invalid_functions
            invalid_func_vms = set()
            for key, val in six.iteritems(invalid_functions):
                invalid_func_vms = invalid_func_vms.union(set(val))

            # Find the VMs that are in names, but not in set of invalid functions.
            missing_vms = names.difference(invalid_func_vms)
            if missing_vms:
                ret['Not Found'] = list(missing_vms)
                ret['Not Actioned/Not Running'] = list(names)

        if not names:
            return ret

        # Don't return missing VM information for invalid functions until after we've had a
        # Chance to return successful actions. If a function is valid for one driver, but
        # Not another, we want to make sure the successful action is returned properly.
        if missing_vms:
            return ret

        # If we reach this point, the Not Actioned and Not Found lists will be the same,
        # But we want to list both for clarity/consistency with the invalid functions lists.
        ret['Not Actioned/Not Running'] = list(names)
        ret['Not Found'] = list(names)
        return ret

    def do_function(self, prov, func, kwargs):
        '''
        Perform a function against a cloud provider
        '''
        matches = self.lookup_providers(prov)
        if len(matches) > 1:
            raise SaltCloudSystemExit(
                'More than one results matched \'{0}\'. Please specify '
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
                'The \'{0}\' cloud provider alias, for the \'{1}\' driver, does '
                'not define the function \'{2}\''.format(alias, driver, func)
            )

        log.debug(
            'Trying to execute \'{0}\' with the following kwargs: {1}'.format(
                fun, kwargs
            )
        )

        with salt.utils.context.func_globals_inject(
            self.clouds[fun],
            __active_provider_name__=':'.join([alias, driver])
        ):
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

    def __filter_non_working_providers(self):
        '''
        Remove any mis-configured cloud providers from the available listing
        '''
        for alias, drivers in six.iteritems(self.opts['providers'].copy()):
            for driver in drivers.copy():
                fun = '{0}.get_configured_provider'.format(driver)
                if fun not in self.clouds:
                    # Mis-configured provider that got removed?
                    log.warning(
                        'The cloud driver, \'{0}\', configured under the '
                        '\'{1}\' cloud provider alias, could not be loaded. '
                        'Please check your provider configuration files and '
                        'ensure all required dependencies are installed '
                        'for the \'{0}\' driver.\n'
                        'In rare cases, this could indicate the \'{2}()\' '
                        'function could not be found.\nRemoving \'{0}\' from '
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

                with salt.utils.context.func_globals_inject(
                    self.clouds[fun],
                    __active_provider_name__=':'.join([alias, driver])
                ):
                    if self.clouds[fun]() is False:
                        log.warning(
                            'The cloud driver, \'{0}\', configured under the '
                            '\'{1}\' cloud provider alias is not properly '
                            'configured. Removing it from the available '
                            'providers list.'.format(driver, alias)
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

        for profile, mapped_vms in six.iteritems(rendered_map):
            names = set(mapped_vms)
            if profile not in self.opts['profiles']:
                if 'Errors' not in interpolated_map:
                    interpolated_map['Errors'] = {}
                msg = (
                    'No provider for the mapped \'{0}\' profile was found. '
                    'Skipped VMS: {1}'.format(
                        profile, ', '.join(names)
                    )
                )
                log.info(msg)
                interpolated_map['Errors'][profile] = msg
                continue

            matching = self.get_running_by_names(names, query, cached)
            for alias, drivers in six.iteritems(matching):
                for driver, vms in six.iteritems(drivers):
                    for vm_name, vm_details in six.iteritems(vms):
                        if alias not in interpolated_map:
                            interpolated_map[alias] = {}
                        if driver not in interpolated_map[alias]:
                            interpolated_map[alias][driver] = {}
                        interpolated_map[alias][driver][vm_name] = vm_details
                        try:
                            names.remove(vm_name)
                        except KeyError:
                            # If it's not there, then our job is already done
                            pass

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
        for alias, drivers in six.iteritems(query_map.copy()):
            for driver, vms in six.iteritems(drivers.copy()):
                for vm_name, vm_details in six.iteritems(vms.copy()):
                    if vm_details == 'Absent':
                        query_map[alias][driver].pop(vm_name)
                if not query_map[alias][driver]:
                    query_map[alias].pop(driver)
            if not query_map[alias]:
                query_map.pop(alias)
        return query_map

    def get_vmnames_by_action(self, action):
        query_map = self.interpolated_map("list_nodes")
        matching_states = {
            'start': ['stopped'],
            'stop': ['running', 'active'],
            'reboot': ['running', 'active'],
        }
        vm_names = []
        for alias, drivers in six.iteritems(query_map):
            for driver, vms in six.iteritems(drivers):
                for vm_name, vm_details in six.iteritems(vms):
                    # Only certain actions are support in to use in this case. Those actions are the
                    # "Global" salt-cloud actions defined in the "matching_states" dictionary above.
                    # If a more specific action is passed in, we shouldn't stack-trace - exit gracefully.
                    try:
                        state_action = matching_states[action]
                    except KeyError:
                        log.error(
                            'The use of \'{0}\' as an action is not supported in this context. '
                            'Only \'start\', \'stop\', and \'reboot\' are supported options.'.format(action)
                        )
                        raise SaltCloudException()
                    if vm_details != 'Absent' and vm_details['state'].lower() in state_action:
                        vm_names.append(vm_name)
        return vm_names

    def read(self):
        '''
        Read in the specified map file and return the map structure
        '''
        map_ = None
        if self.opts.get('map', None) is None:
            if self.opts.get('map_data', None) is None:
                return {}
            else:
                map_ = self.opts['map_data']

        if not map_:
            local_minion_opts = copy.deepcopy(self.opts)
            local_minion_opts['file_client'] = 'local'
            self.minion = salt.minion.MasterMinion(local_minion_opts)

            if not os.path.isfile(self.opts['map']):
                if not (self.opts['map']).startswith('salt://'):
                    log.error(
                        'The specified map file does not exist: \'{0}\''.format(
                            self.opts['map'])
                    )
                    raise SaltCloudNotFound()
            if (self.opts['map']).startswith('salt://'):
                cached_map = self.minion.functions['cp.cache_file'](self.opts['map'])
            else:
                cached_map = self.opts['map']
            try:
                renderer = self.opts.get('renderer', 'yaml_jinja')
                rend = salt.loader.render(self.opts, {})
                blacklist = self.opts.get('renderer_blacklist')
                whitelist = self.opts.get('renderer_whitelist')
                map_ = compile_template(
                    cached_map, rend, renderer, blacklist, whitelist
                )
            except Exception as exc:
                log.error(
                    'Rendering map {0} failed, render error:\n{1}'.format(
                        self.opts['map'], exc
                    ),
                    exc_info_on_loglevel=logging.DEBUG
                )
                return {}

        if 'include' in map_:
            map_ = salt.config.include_config(
                map_, self.opts['map'], verbose=False
            )

        # Create expected data format if needed
        for profile, mapped in six.iteritems(map_.copy()):
            if isinstance(mapped, (list, tuple)):
                entries = {}
                for mapping in mapped:
                    if isinstance(mapping, six.string_types):
                        # Foo:
                        #   - bar1
                        #   - bar2
                        mapping = {mapping: None}
                    for name, overrides in six.iteritems(mapping):
                        if overrides is None or isinstance(overrides, bool):
                            # Foo:
                            #   - bar1:
                            #   - bar2:
                            overrides = {}
                        try:
                            overrides.setdefault('name', name)
                        except AttributeError:
                            log.error(
                                'Cannot use \'name\' as a minion id in a cloud map as it '
                                'is a reserved word. Please change \'name\' to a different '
                                'minion id reference.'
                            )
                            return {}
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
                for name, overrides in six.iteritems(mapped):
                    overrides.setdefault('name', name)
                    entries[name] = overrides
                map_[profile] = entries
                continue

            if isinstance(mapped, six.string_types):
                # If it's a single string entry, let's make iterable because of
                # the next step
                mapped = [mapped]

            map_[profile] = {}
            for name in mapped:
                map_[profile][name] = {'name': name}
        return map_

    def _has_loop(self, dmap, seen=None, val=None):
        if seen is None:
            for values in six.itervalues(dmap['create']):
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
        for profile_name, nodes in six.iteritems(self.rendered_map):
            if profile_name not in self.opts['profiles']:
                msg = (
                    'The required profile, \'{0}\', defined in the map '
                    'does not exist. The defined nodes, {1}, will not '
                    'be created.'.format(
                        profile_name,
                        ', '.join('\'{0}\''.format(node) for node in nodes)
                    )
                )
                log.error(msg)
                if 'errors' not in ret:
                    ret['errors'] = {}
                ret['errors'][profile_name] = msg
                continue

            profile_data = self.opts['profiles'].get(profile_name)

            # Get associated provider data, in case something like size
            # or image is specified in the provider file. See issue #32510.
            alias, driver = profile_data.get('provider').split(':')
            provider_details = self.opts['providers'][alias][driver].copy()
            del provider_details['profiles']

            # Update the provider details information with profile data
            # Profile data should override provider data, if defined.
            # This keeps map file data definitions consistent with -p usage.
            provider_details.update(profile_data)
            profile_data = provider_details

            for nodename, overrides in six.iteritems(nodes):
                # Get the VM name
                nodedata = copy.deepcopy(profile_data)
                # Update profile data with the map overrides
                for setting in ('grains', 'master', 'minion', 'volumes',
                                'requires'):
                    deprecated = 'map_{0}'.format(setting)
                    if deprecated in overrides:
                        log.warning(
                            'The use of \'{0}\' on the \'{1}\' mapping has '
                            'been deprecated. The preferred way now is to '
                            'just define \'{2}\'. For now, salt-cloud will do '
                            'the proper thing and convert the deprecated '
                            'mapping into the preferred one.'.format(
                                deprecated, nodename, setting
                            )
                        )
                        overrides[setting] = overrides.pop(deprecated)

                # merge minion grains from map file
                if 'minion' in overrides and \
                        'minion' in nodedata and \
                        'grains' in overrides['minion'] and \
                        'grains' in nodedata['minion']:
                    nodedata['minion']['grains'].update(
                        overrides['minion']['grains']
                    )
                    del overrides['minion']['grains']
                    # remove minion key if now is empty dict
                    if len(overrides['minion']) == 0:
                        del overrides['minion']

                nodedata = salt.utils.dictupdate.update(nodedata, overrides)
                # Add the computed information to the return data
                ret['create'][nodename] = nodedata
                # Add the node name to the defined set
                alias, driver = nodedata['provider'].split(':')
                defined.add((alias, driver, nodename))

        def get_matching_by_name(name):
            matches = {}
            for alias, drivers in six.iteritems(pmap):
                for driver, vms in six.iteritems(drivers):
                    for vm_name, details in six.iteritems(vms):
                        if vm_name == name and driver not in matches:
                            matches[driver] = details['state']
            return matches

        for alias, drivers in six.iteritems(pmap):
            for driver, vms in six.iteritems(drivers):
                for name, details in six.iteritems(vms):
                    exist.add((alias, driver, name))
                    if name not in ret['create']:
                        continue

                    # The machine is set to be created. Does it already exist?
                    matching = get_matching_by_name(name)
                    if not matching:
                        continue

                    # A machine by the same name exists
                    for item in matching:
                        if name not in ret['create']:
                            # Machine already removed
                            break

                        log.warning("'{0}' already exists, removing from "
                                    'the create map.'.format(name))

                        if 'existing' not in ret:
                            ret['existing'] = {}
                        ret['existing'][name] = ret['create'].pop(name)

        if 'hard' in self.opts and self.opts['hard']:
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
        # Go through the create list and calc dependencies
        for key, val in six.iteritems(dmap['create']):
            log.info('Calculating dependencies for {0}'.format(key))
            level = 0
            level = self._calcdep(dmap, key, val, level)
            log.debug('Got execution order {0} for {1}'.format(level, key))
            dmap['create'][key]['level'] = level

        try:
            existing_list = six.iteritems(dmap['existing'])
        except KeyError:
            existing_list = six.iteritems({})

        for key, val in existing_list:
            log.info('Calculating dependencies for {0}'.format(key))
            level = 0
            level = self._calcdep(dmap, key, val, level)
            log.debug('Got execution order {0} for {1}'.format(level, key))
            dmap['existing'][key]['level'] = level

        # Now sort the create list based on dependencies
        create_list = sorted(six.iteritems(dmap['create']), key=lambda x: x[1]['level'])
        output = {}
        if self.opts['parallel']:
            parallel_data = []
        master_name = None
        master_minion_name = None
        master_host = None
        master_finger = None
        try:
            master_name, master_profile = next((
                (name, profile) for name, profile in create_list
                if profile.get('make_master', False) is True
            ))
            master_minion_name = master_name
            log.debug('Creating new master \'{0}\''.format(master_name))
            if salt.config.get_cloud_config_value(
                'deploy',
                master_profile,
                self.opts
            ) is False:
                raise SaltCloudSystemExit(
                    'Cannot proceed with \'make_master\' when salt deployment '
                    'is disabled(ex: --no-deploy).'
                )

            # Generate the master keys
            log.debug(
                'Generating master keys for \'{0[name]}\''.format(master_profile)
            )
            priv, pub = salt.utils.cloud.gen_keys(
                salt.config.get_cloud_config_value(
                    'keysize',
                    master_profile,
                    self.opts
                )
            )
            master_profile['master_pub'] = pub
            master_profile['master_pem'] = priv

            # Generate the fingerprint of the master pubkey in order to
            # mitigate man-in-the-middle attacks
            master_temp_pub = salt.utils.files.mkstemp()
            with salt.utils.files.fopen(master_temp_pub, 'w') as mtp:
                mtp.write(pub)
            master_finger = salt.utils.crypt.pem_finger(master_temp_pub, sum_type=self.opts['hash_type'])
            os.unlink(master_temp_pub)

            if master_profile.get('make_minion', True) is True:
                master_profile.setdefault('minion', {})
                if 'id' in master_profile['minion']:
                    master_minion_name = master_profile['minion']['id']
                # Set this minion's master as local if the user has not set it
                if 'master' not in master_profile['minion']:
                    master_profile['minion']['master'] = '127.0.0.1'
                    if master_finger is not None:
                        master_profile['master_finger'] = master_finger

            # Generate the minion keys to pre-seed the master:
            for name, profile in create_list:
                make_minion = salt.config.get_cloud_config_value(
                    'make_minion', profile, self.opts, default=True
                )
                if make_minion is False:
                    continue

                log.debug(
                    'Generating minion keys for \'{0[name]}\''.format(profile)
                )
                priv, pub = salt.utils.cloud.gen_keys(
                    salt.config.get_cloud_config_value(
                        'keysize',
                        profile,
                        self.opts
                    )
                )
                profile['pub_key'] = pub
                profile['priv_key'] = priv
                # Store the minion's public key in order to be pre-seeded in
                # the master
                master_profile.setdefault('preseed_minion_keys', {})
                master_profile['preseed_minion_keys'].update({name: pub})

            local_master = False
            if master_profile['minion'].get('local_master', False) and \
                    master_profile['minion'].get('master', None) is not None:
                # The minion is explicitly defining a master and it's
                # explicitly saying it's the local one
                local_master = True

            out = self.create(master_profile, local_master=local_master)

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

            master_host = deploy_kwargs.get('salt_host', deploy_kwargs.get('host', None))
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
                master_finger = salt.utils.crypt.pem_finger(master_pub, sum_type=self.opts['hash_type'])

        opts = self.opts.copy()
        if self.opts['parallel']:
            # Force display_ssh_output to be False since the console will
            # need to be reset afterwards
            log.info(
                'Since parallel deployment is in use, ssh console output '
                'is disabled. All ssh output will be logged though'
            )
            opts['display_ssh_output'] = False

        local_master = master_name is None

        for name, profile in create_list:
            if name in (master_name, master_minion_name):
                # Already deployed, it's the master's minion
                continue

            if 'minion' in profile and profile['minion'].get('local_master', False) and \
                    profile['minion'].get('master', None) is not None:
                # The minion is explicitly defining a master and it's
                # explicitly saying it's the local one
                local_master = True

            if master_finger is not None and local_master is False:
                profile['master_finger'] = master_finger

            if master_host is not None:
                profile.setdefault('minion', {})
                profile['minion'].setdefault('master', master_host)

            if self.opts['parallel']:
                parallel_data.append({
                    'opts': opts,
                    'name': name,
                    'profile': profile,
                    'local_master': local_master
                })
                continue

            # Not deploying in parallel
            try:
                output[name] = self.create(
                    profile, local_master=local_master
                )
                if self.opts.get('show_deploy_args', False) is False \
                        and 'deploy_kwargs' in output \
                        and isinstance(output[name], dict):
                    output[name].pop('deploy_kwargs', None)
            except SaltCloudException as exc:
                log.error(
                    'Failed to deploy \'{0}\'. Error: {1}'.format(
                        name, exc
                    ),
                    # Show the traceback if the debug logging level is enabled
                    exc_info_on_loglevel=logging.DEBUG
                )
                output[name] = {'Error': str(exc)}

        for name in dmap.get('destroy', ()):
            output[name] = self.destroy(name)

        if self.opts['parallel'] and len(parallel_data) > 0:
            if 'pool_size' in self.opts:
                pool_size = self.opts['pool_size']
            else:
                pool_size = len(parallel_data)
            log.info('Cloud pool size: {0}'.format(pool_size))
            output_multip = enter_mainloop(
                _create_multiprocessing, parallel_data, pool_size=pool_size)
            # We have deployed in parallel, now do start action in
            # correct order based on dependencies.
            if self.opts['start_action']:
                actionlist = []
                grp = -1
                for key, val in groupby(six.itervalues(dmap['create']), lambda x: x['level']):
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
                    client = salt.client.get_local_client()
                    out.update(client.cmd(
                        ','.join(group), self.opts['start_action'],
                        timeout=self.opts['timeout'] * 60, tgt_type='list'
                    ))
                for obj in output_multip:
                    next(six.itervalues(obj))['ret'] = out[next(six.iterkeys(obj))]
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


def create_multiprocessing(parallel_data, queue=None):
    '''
    This function will be called from another process when running a map in
    parallel mode. The result from the create is always a json object.
    '''
    salt.utils.crypt.reinit_crypto()

    parallel_data['opts']['output'] = 'json'
    cloud = Cloud(parallel_data['opts'])
    try:
        output = cloud.create(
            parallel_data['profile'],
            local_master=parallel_data['local_master']
        )
    except SaltCloudException as exc:
        log.error(
            'Failed to deploy \'{0[name]}\'. Error: {1}'.format(
                parallel_data, exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {parallel_data['name']: {'Error': str(exc)}}

    if parallel_data['opts'].get('show_deploy_args', False) is False and isinstance(output, dict):
        output.pop('deploy_kwargs', None)

    return {
        parallel_data['name']: salt.utils.data.simple_types_filter(output)
    }


def destroy_multiprocessing(parallel_data, queue=None):
    '''
    This function will be called from another process when running a map in
    parallel mode. The result from the destroy is always a json object.
    '''
    salt.utils.crypt.reinit_crypto()

    parallel_data['opts']['output'] = 'json'
    clouds = salt.loader.clouds(parallel_data['opts'])

    try:
        fun = clouds['{0}.destroy'.format(parallel_data['driver'])]
        with salt.utils.context.func_globals_inject(
            fun,
            __active_provider_name__=':'.join([
                parallel_data['alias'],
                parallel_data['driver']
            ])
        ):
            output = fun(parallel_data['name'])

    except SaltCloudException as exc:
        log.error(
            'Failed to destroy {0}. Error: {1}'.format(
                parallel_data['name'], exc
            ),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        return {parallel_data['name']: {'Error': str(exc)}}

    return {
        parallel_data['name']: salt.utils.data.simple_types_filter(output)
    }


def run_parallel_map_providers_query(data, queue=None):
    '''
    This function will be called from another process when building the
    providers map.
    '''
    salt.utils.crypt.reinit_crypto()

    cloud = Cloud(data['opts'])
    try:
        with salt.utils.context.func_globals_inject(
            cloud.clouds[data['fun']],
            __active_provider_name__=':'.join([
                data['alias'],
                data['driver']
            ])
        ):
            return (
                data['alias'],
                data['driver'],
                salt.utils.data.simple_types_filter(
                    cloud.clouds[data['fun']]()
                )
            )
    except Exception as err:
        log.debug(
            'Failed to execute \'{0}()\' while querying for running '
            'nodes: {1}'.format(data['fun'], err),
            # Show the traceback if the debug logging level is
            # enabled
            exc_info_on_loglevel=logging.DEBUG
        )
        # Failed to communicate with the provider, don't list any nodes
        return data['alias'], data['driver'], ()


# for pickle and multiprocessing, we can't use directly decorators
def _run_parallel_map_providers_query(*args, **kw):
    return communicator(run_parallel_map_providers_query)(*args[0], **kw)


def _destroy_multiprocessing(*args, **kw):
    return communicator(destroy_multiprocessing)(*args[0], **kw)


def _create_multiprocessing(*args, **kw):
    return communicator(create_multiprocessing)(*args[0], **kw)
