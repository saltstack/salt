'''
Make me some salt!
'''
# Import python libs
import os
import optparse
# Import salt libs
import salt.config


def verify_env(dirs):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    for dir_ in dirs:
        if not os.path.isdir(dir_):
            os.makedirs(dir_)

class Master(object):
    '''
    Creates a master server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = salt.config.master_config(self.cli['config'])

    def __parse_cli(self):
        '''
        Parse the cli for options passed to a master daemon
        '''
        import salt.log
        parser = optparse.OptionParser()
        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Run the master in a daemon')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/master',
                help='Pass in an alternative configuration file')
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                default='warning',
                choices=salt.log.LOG_LEVELS.keys(),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'%%default\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS.keys()])
                )

        options, args = parser.parse_args()
        salt.log.setup_console_logger(options.log_level)

        cli = {'daemon': options.daemon,
               'config': options.config}

        return cli

    def start(self):
        '''
        Run the sequence to start a salt master server
        '''
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)
        import logging
        verify_env([os.path.join(self.opts['pki_dir'], 'minions'),
                    os.path.join(self.opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.opts['cachedir'], 'jobs'),
                    ])
        # Late import so logging works correctly
        import salt.master
        master = salt.master.Master(self.opts)
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()
        master.start()


class Minion(object):
    '''
    Create a minion server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = salt.config.minion_config(self.cli['config'])

    def __parse_cli(self):
        '''
        Parse the cli input
        '''
        import salt.log
        parser = optparse.OptionParser()
        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Run the minion as a daemon')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/minion',
                help='Pass in an alternative configuration file')
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                default='warning',
                choices=salt.log.LOG_LEVELS.keys(),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'%%default\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS.keys()]))

        options, args = parser.parse_args()
        salt.log.setup_console_logger(options.log_level)
        cli = {'daemon': options.daemon,
               'config': options.config}

        return cli

    def start(self):
        '''
        Execute this method to start up a minion.
        '''
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)

        import logging

        verify_env([self.opts['pki_dir'], self.opts['cachedir']])
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()
        # Late import so logging works correctly
        import salt.minion
        minion = salt.minion.Minion(self.opts)
        minion.tune_in()
