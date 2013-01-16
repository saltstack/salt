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
# the VM data will be in opts['vm']

# Import python libs
import optparse
import os

# Import salt libs
import saltcloud.config
import saltcloud.output
import salt.config
import salt.output

# Import saltcloud libs
from saltcloud.utils import parsers
from saltcloud.libcloudfuncs import libcloud_version


class SaltCloud(parsers.SaltCloudParser):
    def run(self):
        '''
        Execute the salt-cloud command line
        '''
        libcloud_version()

        # Parse shell arguments
        self.parse_args()

        # Setup log file logging
        self.setup_logfile_logger()

        # Late imports so logging works as expected
        import logging
        logging.getLogger(__name__).info('salt-cloud starting')
        import saltcloud.cloud
        mapper = saltcloud.cloud.Map(self.config)

        if self.selected_query_option is not None:
            if self.options.map:
                try:
                    query_map = mapper.interpolated_map(
                        query=self.selected_query_option
                    )
                except Exception as exc:
                    print('There was an error: {0}'.format(exc))
            else:
                try:
                    query_map = mapper.map_providers(
                        query=self.selected_query_option
                    )
                except Exception as exc:
                    print('There was an error: {0}'.format(exc))
            salt.output.display_output(query_map, '', self.config)

        if self.options.list_locations is not None:
            try:
                saltcloud.output.double_layer(
                    mapper.location_list(self.options.list_locations)
                )
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)

        if self.options.list_images is not None:
            try:
                saltcloud.output.double_layer(
                    mapper.image_list(self.options.list_images)
                )
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)

        if self.options.list_sizes is not None:
            try:
                saltcloud.output.double_layer(
                    mapper.size_list(self.options.list_sizes)
                )
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)

        if self.options.destroy and (self.config.get('names', None) or
                                     self.options.map):
            if self.options.map:
                names = mapper.delete_map(query='list_nodes')
            else:
                names = self.config.get('names', None)

            try:
                mapper.destroy(names)
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)

        if self.options.action and (self.config.get('names', None) or
                                     self.options.map):
            if self.options.map:
                names = mapper.delete_map(query='list_nodes')
            else:
                names = self.config.get('names', None)

            try:
                mapper.do_action(names)
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)

        if self.options.profile and self.config.get('names', False):
            try:
                mapper.run_profile()
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)

        if self.options.map and self.selected_query_option is None:
            try:
                mapper.run_map()
            except Exception as exc:
                print('There was an error: {0}'.format(exc))
            self.exit(0)
