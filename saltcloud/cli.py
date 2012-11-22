'''
Primary interfaces for the salt-cloud system
'''
# Need to get data from 4 sources!
# CLI options
# salt cloud config - /etc/salt/cloud
# salt master config (for master integration)
# salt vm config, where vms are defined - /etc/salt/cloud.vm
#
# The cli, master and cloud configs will merge for opts
# the vm data will be in opts['vm']

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
                query_map = mapper.interpolated_map(
                    query=self.selected_query_option
                )
            else:
                query_map = mapper.map_providers(
                    query=self.selected_query_option
                )
            salt.output.display_output(query_map, '', self.config)

        if self.options.list_locations is not None:
            saltcloud.output.double_layer(
                mapper.location_list(self.options.list_locations)
            )
            self.exit(0)

        if self.options.list_images is not None:
            saltcloud.output.double_layer(
                mapper.image_list(self.options.list_images)
            )
            self.exit(0)

        if self.options.list_sizes is not None:
            saltcloud.output.double_layer(
                mapper.size_list(self.options.list_sizes)
            )
            self.exit(0)

        if self.options.destroy and (self.config.get('names', None) or
                                     self.options.map):
            if self.options.map:
                names = mapper.delete_map(query='list_nodes')
            else:
                names = self.config.get('names', None)
            mapper.destroy(names)
            self.exit(0)

        if self.options.profile and self.config.get('names', False):
            mapper.run_profile()
            self.exit(0)

        if self.options.map and self.selected_query_option is None:
            mapper.run_map()
            self.exit(0)
