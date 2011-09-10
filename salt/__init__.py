'''
Make me some salt!
'''
# Import python libs
import optparse
import os
import sys
# Import salt libs
import salt.config


def verify_env(dirs):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    for dir_ in dirs:
        if not os.path.isdir(dir_):
            try:
                os.makedirs(dir_)
            except OSError, e:
                print 'Failed to create directory path "%s" - %s' % (dir_, e)

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
        verify_env([os.path.join(self.opts['pki_dir'], 'minions'),
                    os.path.join(self.opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.opts['cachedir'], 'jobs'),
                    os.path.dirname(self.opts['log_file']),
                    self.opts['sock_dir'],
                    ])
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)
        import logging
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
        verify_env([self.opts['pki_dir'], self.opts['cachedir'],
                os.path.dirname(self.opts['log_file']),
                ])
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)

        import logging

        # Late import so logging works correctly
        import salt.minion
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()
        minion = salt.minion.Minion(self.opts)
        minion.tune_in()


class Syndic(object):
    '''
    Create a syndic server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = self.__prep_opts()

    def __prep_opts(self):
        '''
        Generate the opts used by the syndic
        '''
        opts = salt.config.master_config(self.cli['master_config'])
        opts['_minion_conf_file'] = opts['conf_file']
        opts.update(salt.config.minion_config(self.cli['minion_config']))
        if opts.has_key('syndic_master'):
            # Some of the opts need to be changed to match the needed opts
            # in the minion class.
            opts['master'] = opts['syndic_master']
            opts['master_ip'] = salt.config.dns_check(opts['master'])

            opts['master_uri'] = 'tcp://' + opts['master_ip'] + ':'\
                               + str(opts['master_port'])
            opts['_master_conf_file'] = opts['conf_file']
            opts.pop('conf_file')
            return opts
        err = 'The syndic_master needs to be configured in the salt master'\
            + ' config, EXITING!\n'
        sys.stderr.write(err)
        sys.exit(2)

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
        parser.add_option('--master-config',
                dest='master_config',
                default='/etc/salt/master',
                help='Pass in an alternative master configuration file')
        parser.add_option('--minion-config',
                dest='minion_config',
                default='/etc/salt/minion',
                help='Pass in an alternative minion configuration file')
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
               'minion_config': options.minion_config,
               'master_config': options.master_config,
               }

        return cli

    def start(self):
        '''
        Execute this method to start up a syndic.
        '''
        verify_env([self.opts['pki_dir'], self.opts['cachedir'],
                os.path.dirname(self.opts['log_file']),
                ])
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)

        import logging

        # Late import so logging works correctly
        import salt.minion
        syndic = salt.minion.Syndic(self.opts)
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()
        syndic.tune_in()
