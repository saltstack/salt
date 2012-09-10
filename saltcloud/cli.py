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
import pprint

# Import salt libs
import saltcloud.config
import saltcloud.output
import salt.config
import salt.output

from saltcloud.version import __version__ as VERSION

class SaltCloud(object):
    '''
    Create a cli SaltCloud object
    '''
    def __init__(self):
        self.opts = self.parse()

    def parse(self):
        '''
        Parse the command line and merge the config
        '''
        # Grab data from the 4 sources
        cli = self._parse_cli()
        cloud = saltcloud.config.cloud_config(cli['cloud_config'])
        opts = salt.config.master_config(cli['master_config'])
        vms = saltcloud.config.vm_config(cli['vm_config'])
        
        # Load the data in order
        opts.update(cloud)
        opts.update(cli)
        opts['vm'] = vms
        
        return opts

    def _parse_cli(self):
        '''
        Parse the cli and return a dict of the options
        '''
        parser = optparse.OptionParser()

        parser.add_option(
                '--version',
                dest='version',
                default=False,
                action='store_true',
                help='Show program version number and exit')

        parser.add_option('-p',
                '--profile',
                dest='profile',
                default='',
                help='Specify a profile to use for the vms')

        parser.add_option('-m',
                '--map',
                dest='map',
                default='',
                help='Specify a cloud map file to use for deployment')

        parser.add_option('-H',
                '--hard',
                dest='hard',
                default=False,
                action='store_true',
                help=('Delete all vms that are not defined in the map file '
                      'CAUTION!!! This operation can irrevocably destroy vms!')
                )

        parser.add_option('-d',
                '--destroy',
                dest='destroy',
                default=False,
                action='store_true',
                help='Specify a vm to destroy')

        parser.add_option('-P',
                '--parallel',
                dest='parallel',
                default=False,
                action='store_true',
                help='Build all of the specified virtual machines in parallel')

        parser.add_option('-Q',
                '--query',
                dest='query',
                default=False,
                action='store_true',
                help=('Execute a query and return information about the nodes '
                      'running on configured cloud providers'))

        parser.add_option('--list-images',
                dest='list_images',
                default=False,
                help=('Display a list of images available in configured '
                      'cloud providers. Pass the cloud provider that '
                      'available images are desired on, aka "linode", '
                      'or pass "all" to list images for all configured '
                      'cloud providers'))

        parser.add_option('--list-sizes',
                dest='list_sizes',
                default=False,
                help=('Display a list of sizes available in configured '
                      'cloud providers. Pass the cloud provider that '
                      'available sizes are desired on, aka "AWS", '
                      'or pass "all" to list sizes for all configured '
                      'cloud providers'))

        parser.add_option('-C',
                '--cloud-config',
                dest='cloud_config',
                default='/etc/salt/cloud',
                help='The location of the saltcloud config file')

        parser.add_option('-M',
                '--master-config',
                dest='master_config',
                default='/etc/salt/master',
                help='The location of the salt master config file')

        parser.add_option('-V',
                '--profiles',
                '--vm_config',
                dest='vm_config',
                default='/etc/salt/cloud.profiles',
                help='The location of the saltcloud vm config file')

        parser.add_option('--raw-out',
                default=False,
                action='store_true',
                dest='raw_out',
                help=('Print the output from the salt command in raw python '
                      'form, this is suitable for re-reading the output into '
                      'an executing python script with eval.'))

        parser.add_option('--text-out',
                default=False,
                action='store_true',
                dest='txt_out',
                help=('Print the output from the salt command in the same '
                      'form the shell would.'))

        parser.add_option('--yaml-out',
                default=False,
                action='store_true',
                dest='yaml_out',
                help='Print the output from the salt command in yaml.')

        parser.add_option('--json-out',
                default=False,
                action='store_true',
                dest='json_out',
                help='Print the output from the salt command in json.')

        parser.add_option('--no-color',
                default=False,
                action='store_true',
                dest='no_color',
                help='Disable all colored output')

        options, args = parser.parse_args()

        cli = {}

        for k, v in options.__dict__.items():
            if v is not None:
                cli[k] = v
        if args:
            cli['names'] = args

        return cli

    def run(self):
        '''
        Exeute the salt cloud execution run
        '''
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
            )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)
        import logging
        # If statement here for when cloud query is added
        import saltcloud.cloud
        mapper = saltcloud.cloud.Map(self.opts)

        if self.opts['query']:
            get_outputter = salt.output.get_outputter
            if self.opts['raw_out']:
                printout = get_outputter('raw')
            elif self.opts['json_out']:
                printout = get_outputter('json')
            elif self.opts['txt_out']:
                printout = get_outputter('txt')
            elif self.opts['yaml_out']:
                printout = get_outputter('yaml')
            else:
                printout = get_outputter(None)

            color = not bool(self.opts['no_color'])
            printout(mapper.map_providers(), color=color)

        if self.opts['version']:
            print VERSION
        if self.opts['list_images']:
            saltcloud.output.double_layer(
                    mapper.image_list(self.opts['list_images'])
                    )
        if self.opts['list_sizes']:
            saltcloud.output.double_layer(
                    mapper.size_list(self.opts['list_sizes'])
                    )
        elif self.opts.get('names') and self.opts['destroy']:
            mapper.destroy(self.opts.get('names'))
        elif self.opts.get('names', False) and self.opts['profile']:
            mapper.run_profile()
        elif self.opts['map']:
            mapper.run_map()
