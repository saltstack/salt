'''
Primary interfaces for the salt-cloud system
'''
# Need to get data from 4 sources!
# CLI options
# salt cloud config - /etc/salt/cloud
# salt master config (for master integration)
# salt VM config, where VMs are defined - /etc/salt/cloud.profiles
#
# The cli, master and cloud configs will merge for opts
# the VM data will be in opts['profiles']

# Import python libs
import os
import sys
import getpass
import logging

# Import salt libs
import salt.config
import salt.output
import salt.utils
from salt.utils.verify import check_user, verify_env, verify_files

# Import saltcloud libs
import saltcloud.cloud
import saltcloud.config
from saltcloud.utils import parsers
from saltcloud.exceptions import SaltCloudException, SaltCloudSystemExit
from saltcloud.libcloudfuncs import libcloud_version


log = logging.getLogger(__name__)


class SaltCloud(parsers.SaltCloudParser):
    def run(self):
        '''
        Execute the salt-cloud command line
        '''
        libcloud_version()

        # Parse shell arguments
        self.parse_args()

        salt_master_user = self.config.get('user', getpass.getuser())
        if salt_master_user is not None and not check_user(salt_master_user):
            self.error(
                'salt-cloud needs to run as the same user as salt-master, '
                '{0!r}, but was unable to switch credentials. Please run '
                'salt-cloud as root or as {0!r}'.format(salt_master_user)
            )

        try:
            if self.config['verify_env']:
                verify_env(
                    [os.path.dirname(self.config['conf_file'])],
                    salt_master_user
                )
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith('tcp://') \
                        and not logfile.startswith('udp://') \
                        and not logfile.startswith('file://'):
                    # Logfile is not using Syslog, verify
                    verify_files([logfile], salt_master_user)
        except (IOError, OSError) as err:
            log.error('Error while verifying the environment: {0}'.format(err))
            sys.exit(err.errno)

        # Setup log file logging
        self.setup_logfile_logger()

        if self.options.update_bootstrap:
            import urllib2
            url = 'http://bootstrap.saltstack.org'
            req = urllib2.urlopen(url)
            if req.getcode() != 200:
                self.error(
                    'Failed to download the latest stable version of the '
                    'bootstrap-salt.sh script from {0}. HTTP error: '
                    '{1}'.format(
                        url, req.getcode()
                    )
                )

            for entry in self.config.get('deploy_scripts_search_path'):
                deploy_path = os.path.join(entry, 'bootstrap-salt.sh')
                try:
                    print(
                        'Updating bootstrap-salt.sh.'
                        '\n\tSource:      {0}'
                        '\n\tDestination: {1}'.format(
                            url,
                            deploy_path
                        )
                    )
                    with salt.utils.fopen(deploy_path, 'w') as fp_:
                        fp_.write(req.read())
                    # We were able to update, no need to continue trying to
                    # write up the search path
                    self.exit(0)
                except (OSError, IOError), err:
                    log.debug(
                        'Failed to write the updated script: {0}'.format(err)
                    )
                    continue
            self.error('Failed to update the bootstrap script')

        log.info('salt-cloud starting')
        mapper = saltcloud.cloud.Map(self.config)

        ret = {}

        if self.selected_query_option is not None:
            if self.selected_query_option == 'list_providers':
                try:
                    display_output = salt.output.get_printout(
                        self.options.output, self.config
                    )
                    print(display_output(mapper.provider_list()))
                    self.exit(0)
                except (SaltCloudException, Exception) as exc:
                    msg = 'There was an error listing providers: {0}'
                    self.handle_exception(msg, exc)

            if self.config.get('map', None):
                log.info('Applying map from {0!r}.'.format(self.config['map']))
                try:
                    ret = mapper.interpolated_map(
                        query=self.selected_query_option
                    )
                except (SaltCloudException, Exception) as exc:
                    msg = 'There was an error with a custom map: {0}'
                    self.handle_exception(msg, exc)
            else:
                try:
                    ret = mapper.map_providers_parallel(
                        query=self.selected_query_option
                    )
                except (SaltCloudException, Exception) as exc:
                    msg = 'There was an error with a map: {0}'
                    self.handle_exception(msg, exc)

        elif self.options.list_locations is not None:
            try:
                display_output = salt.output.get_printout(
                    self.options.output, self.config
                )
                print(
                    display_output(
                        mapper.location_list(
                            self.options.list_locations
                        )
                    )
                )
                self.exit(0)
            except (SaltCloudException, Exception) as exc:
                msg = 'There was an error listing locations: {0}'
                self.handle_exception(msg, exc)

        elif self.options.list_images is not None:
            try:
                display_output = salt.output.get_printout(
                    self.options.output, self.config
                )
                print(
                    display_output(
                        mapper.image_list(
                            self.options.list_images
                        )
                    )
                )
                self.exit(0)
            except (SaltCloudException, Exception) as exc:
                msg = 'There was an error listing images: {0}'
                self.handle_exception(msg, exc)

        elif self.options.list_sizes is not None:
            try:
                display_output = salt.output.get_printout(
                    self.options.output, self.config
                )
                print(
                    display_output(
                        mapper.size_list(
                            self.options.list_sizes
                        )
                    )
                )
                self.exit(0)
            except (SaltCloudException, Exception) as exc:
                msg = 'There was an error listing sizes: {0}'
                self.handle_exception(msg, exc)

        elif self.options.destroy and (self.config.get('names', None) or
                                       self.config.get('map', None)):
            if self.config.get('map', None):
                log.info('Applying map from {0!r}.'.format(self.config['map']))
                matching = mapper.delete_map(query='list_nodes')
            else:
                matching = mapper.get_running_by_names(
                    self.config.get('names', ())
                )

            if not matching:
                print('No machines were found to be destroyed')
                self.exit()

            msg = 'The following virtual machines are set to be destroyed:\n'
            names = set()
            for alias, drivers in matching.iteritems():
                msg += '  {0}:\n'.format(alias)
                for driver, vms in drivers.iteritems():
                    msg += '    {0}:\n'.format(driver)
                    for name in vms:
                        msg += '      {0}\n'.format(name)
                        names.add(name)
            try:
                if self.print_confirm(msg):
                    ret = mapper.destroy(names, cached=True)
            except (SaltCloudException, Exception) as exc:
                msg = 'There was an error destroying machines: {0}'
                self.handle_exception(msg, exc)

        elif self.options.action and (self.config.get('names', None) or
                                      self.config.get('map', None)):
            if self.config.get('map', None):
                log.info('Applying map from {0!r}.'.format(self.config['map']))
                names = mapper.delete_map(query='list_nodes')
            else:
                names = self.config.get('names', None)

            kwargs = {}
            machines = []
            msg = (
                'The following virtual machines are set to be actioned with '
                '"{0}":\n'.format(
                    self.options.action
                )
            )
            for name in names:
                if '=' in name:
                    # This is obviously not a machine name, treat it as a kwarg
                    comps = name.split('=')
                    kwargs[comps[0]] = comps[1]
                else:
                    msg += '  {0}\n'.format(name)
                    machines.append(name)
            names = machines

            try:
                if self.print_confirm(msg):
                    ret = mapper.do_action(names, kwargs)
            except (SaltCloudException, Exception) as exc:
                msg = 'There was an error actioning machines: {0}'
                self.handle_exception(msg, exc)

        elif self.options.function:
            kwargs = {}
            args = self.args[:]
            for arg in args:
                if '=' in arg:
                    key, value = arg.split('=')
                    kwargs[key] = value
                    args.remove(arg)

            if args:
                self.error(
                    'Any arguments passed to --function need to be passed '
                    'as kwargs. Ex: image=ami-54cf5c3d. Remaining '
                    'arguments: {0}'.format(args)
                )
            try:
                ret = mapper.do_function(
                    self.function_provider, self.function_name, kwargs
                )
            except (SaltCloudException, Exception) as exc:
                msg = 'There was an error running the function: {0}'
                self.handle_exception(msg, exc)

        elif self.options.profile and self.config.get('names', False):
            try:
                ret = mapper.run_profile(
                    self.options.profile,
                    self.config.get('names')
                )
            except (SaltCloudException, Exception) as exc:
                msg = 'There was a profile error: {0}'
                self.handle_exception(msg, exc)

        elif self.config.get('map', None) and \
                self.selected_query_option is None:
            if len(mapper.rendered_map) == 0:
                sys.stderr.write('No nodes defined in this map')
                self.exit(1)
            try:
                log.info('Applying map from {0!r}.'.format(self.config['map']))
                dmap = mapper.map_data()

                msg = ''
                if 'errors' in dmap:
                    msg += 'Found the following errors:\n'
                    for profile_name, error in dmap['errors'].iteritems():
                        msg += '  {0}: {1}\n'.format(profile_name, error)

                if 'existing' in dmap:
                    msg += ('The following virtual machines were found '
                            'already running:\n')
                    for name in dmap['existing']:
                        msg += '  {0}\n'.format(name)

                if dmap['create']:
                    msg += ('The following virtual machines are set to be '
                            'created:\n')
                    for name in dmap['create']:
                        msg += '  {0}\n'.format(name)

                if 'destroy' in dmap:
                    msg += ('The following virtual machines are set to be '
                            'destroyed:\n')
                    for name in dmap['destroy']:
                        msg += '  {0}\n'.format(name)

                if not dmap['create'] and not dmap.get('destroy', None):
                    print(msg)
                    self.exit(1)

                if self.print_confirm(msg):
                    ret = mapper.run_map(dmap)

                if self.config.get('parallel', False) is False:
                    log.info('Complete')

            except (SaltCloudException, Exception) as exc:
                msg = 'There was a query error: {0}'
                self.handle_exception(msg, exc)

        else:
            self.error('Nothing was done. Using the proper arguments?')

        display_output = salt.output.get_printout(
            self.options.output, self.config
        )
        # display output using salt's outputter system
        print(display_output(ret))
        self.exit(0)

    def print_confirm(self, msg):
        if self.options.assume_yes:
            return True
        print(msg)
        res = raw_input('Proceed? [N/y] ')
        if not res.lower().startswith('y'):
            return False
        print('... proceeding')
        return True

    def handle_exception(self, msg, exc):
        if isinstance(exc, SaltCloudException):
            # It's a know exception an we know own to handle it
            if isinstance(exc, SaltCloudSystemExit):
                # This is a salt cloud system exit
                if exc.exit_code > 0:
                    # the exit code is bigger than 0, it's an error
                    msg = 'Error: {0}'.format(msg)
                self.exit(
                    exc.exit_code,
                    '{0}\n'.format(
                        msg.format(exc.message.rstrip())
                    )
                )
            # It's not a system exit but it's an error we can
            # handle
            self.error(
                msg.format(exc.message)
            )
        # This is a generic exception, log it, include traceback if
        # debug logging is enabled and exit.
        log.error(
            msg.format(exc),
            # Show the traceback if the debug logging level is
            # enabled
            exc_info=log.isEnabledFor(logging.DEBUG)
        )
        self.exit(1)
