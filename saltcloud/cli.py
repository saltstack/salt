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
import salt.config

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
                '--vm-config',
                dest='vm_config',
                default='/etc/salt/cloud.vm',
                help='The location of the saltcloud vm config file')

        options, args = parser.parse_args()

        cli = {}

        for k, v in options.__dict__.items():
            if v is not None:
                cli[k] = v
        if args:
            cli['name'] = args[0]

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
        import saltcloud
        cloud = saltcloud.Cloud(self.opts)
        cloud.run()

