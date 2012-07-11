'''
Make me some salt!
'''
from salt.version import __version__

# Import python libs
import os
import sys
import optparse

# Import salt libs, the try block bypasses an issue at build time so that c
# modules don't cause the build to fail
try:
    import salt.config
    from salt.utils.process import set_pidfile
    from salt.utils.verify import check_user, verify_env, verify_socket
except ImportError as e:
    if e.args[0] != 'No module named _msgpack':
        raise

class Master(object):
    '''
    Creates a master server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        # command line overrides config
        if self.cli['user']:
            self.opts['user'] = self.cli['user']

        # Send the pidfile location to the opts
        if self.cli['pidfile']:
            self.opts['pidfile'] = self.cli['pidfile']

    def __parse_cli(self):
        '''
        Parse the cli for options passed to a master daemon
        '''
        import salt.log
        parser = optparse.OptionParser(version="%%prog %s" % __version__)
        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Run the master as a daemon')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/master',
                help='Pass in an alternative configuration file')
        parser.add_option('-u',
                '--user',
                dest='user',
                help='Specify user to run master')
        parser.add_option('--pid-file',
                dest='pidfile',
                help=('Specify the location of the pidfile.'))
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                choices=list(salt.log.LOG_LEVELS),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'warning\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS]))

        options, args = parser.parse_args()

        self.opts = salt.config.master_config(options.config)

        if not options.log_level:
            options.log_level = self.opts['log_level']

        salt.log.setup_console_logger(
            options.log_level,
            log_format=self.opts['log_fmt_console'],
            date_format=self.opts['log_datefmt']
        )

        cli = {'daemon': options.daemon,
               'config': options.config,
               'user': options.user,
               'pidfile': options.pidfile}

        return cli

    def start(self):
        '''
        Run the sequence to start a salt master server
        '''
        try:
            verify_env([
                self.opts['pki_dir'],
                os.path.join(self.opts['pki_dir'], 'minions'),
                os.path.join(self.opts['pki_dir'], 'minions_pre'),
                os.path.join(self.opts['pki_dir'], 'minions_rejected'),
                self.opts['cachedir'],
                os.path.join(self.opts['cachedir'], 'jobs'),
                os.path.dirname(self.opts['log_file']),
                self.opts['sock_dir'],
            ], self.opts['user'])
        except OSError, err:
            sys.exit(err.errno)

        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'],
            self.opts['log_level_logfile'] or self.opts['log_level'],
            log_format=self.opts['log_fmt_logfile'],
            date_format=self.opts['log_datefmt']
        )
        for name, level in self.opts['log_granular_levels'].items():
            salt.log.set_logger_level(name, level)

        import logging
        log = logging.getLogger(__name__)
        # Late import so logging works correctly
        if not verify_socket(
                self.opts['interface'],
                self.opts['publish_port'],
                self.opts['ret_port']
                ):
            log.critical('The ports are not available to bind')
            sys.exit(4)

        import salt.master
        master = salt.master.Master(self.opts)
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()
        set_pidfile(self.opts['pidfile'])
        if check_user(self.opts['user'], log):
            try:
                master.start()
            except salt.master.MasterExit:
                sys.exit()


class Minion(object):
    '''
    Create a minion server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        # command line overrides config
        if self.cli['user']:
            self.opts['user'] = self.cli['user']

    def __parse_cli(self):
        '''
        Parse the cli input
        '''
        import salt.log
        parser = optparse.OptionParser(version="%%prog %s" % __version__)
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
        parser.add_option('-u',
                '--user',
                dest='user',
                help='Specify user to run minion')
        parser.add_option('--pid-file',
                dest='pidfile',
                default='/var/run/salt-minion.pid',
                help=('Specify the location of the pidfile. Default'
                      ' %default'))
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                choices=list(salt.log.LOG_LEVELS),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'warning\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS]))

        options, args = parser.parse_args()

        self.opts = salt.config.minion_config(options.config)

        if not options.log_level:
            options.log_level = self.opts['log_level']

        salt.log.setup_console_logger(
            options.log_level,
            log_format=self.opts['log_fmt_console'],
            date_format=self.opts['log_datefmt']
        )

        cli = {'daemon': options.daemon,
               'config': options.config,
               'user': options.user,
               'pidfile': options.pidfile}

        return cli

    def start(self):
        '''
        Execute this method to start up a minion.
        '''
        try:
            verify_env([
                self.opts['pki_dir'],
                self.opts['cachedir'],
                self.opts['sock_dir'],
                self.opts['extension_modules'],
                os.path.dirname(self.opts['log_file']),
            ], self.opts['user'])
        except OSError, err:
            sys.exit(err.errno)

        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'],
            self.opts['log_level_logfile'] or self.opts['log_level'],
            log_format=self.opts['log_fmt_logfile'],
            date_format=self.opts['log_datefmt']
        )
        for name, level in self.opts['log_granular_levels'].items():
            salt.log.set_logger_level(name, level)

        import logging
        # Late import so logging works correctly
        import salt.minion
        log = logging.getLogger(__name__)
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            # If the minion key has not been accepted, then Salt enters a loop
            # waiting for it, if we daemonize later then the minion could halt
            # the boot process waiting for a key to be accepted on the master.
            # This is the latest safe place to daemonize
            salt.utils.daemonize()
        try:
            minion = salt.minion.Minion(self.opts)
            set_pidfile(self.cli['pidfile'])
            if check_user(self.opts['user'], log):
                minion.tune_in()
        except KeyboardInterrupt:
            log.warn('Stopping the Salt Minion')
            raise SystemExit('\nExiting on Ctrl-c')


class Syndic(object):
    '''
    Create a syndic server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        # command line overrides config
        if self.cli['user']:
            self.opts['user'] = self.cli['user']

    def __prep_opts(self, cli):
        '''
        Generate the opts used by the syndic
        '''
        opts = salt.config.master_config(cli['master_config'])
        opts['_minion_conf_file'] = opts['conf_file']
        opts.update(salt.config.minion_config(cli['minion_config']))
        if 'syndic_master' in opts:
            # Some of the opts need to be changed to match the needed opts
            # in the minion class.
            opts['master'] = opts['syndic_master']
            opts['master_ip'] = salt.utils.dns_check(opts['master'])

            opts['master_uri'] = ('tcp://' + opts['master_ip'] +
                                  ':' + str(opts['master_port']))
            opts['_master_conf_file'] = opts['conf_file']
            opts.pop('conf_file')
            return opts
        err = ('The syndic_master needs to be configured in the salt master '
               'config, EXITING!\n')
        sys.stderr.write(err)
        sys.exit(2)

    def __parse_cli(self):
        '''
        Parse the cli for options passed to a syndic daemon
        '''
        import salt.log
        parser = optparse.OptionParser(version="%%prog %s" % __version__)
        parser.add_option('-d',
                '--daemon',
                dest='daemon',
                default=False,
                action='store_true',
                help='Run the syndic as a daemon')
        parser.add_option('--master-config',
                dest='master_config',
                default='/etc/salt/master',
                help='Pass in an alternative master configuration file')
        parser.add_option('--minion-config',
                dest='minion_config',
                default='/etc/salt/minion',
                help='Pass in an alternative minion configuration file')
        parser.add_option('-u',
                '--user',
                dest='user',
                help='Specify user to run syndic')
        parser.add_option('--pid-file',
                dest='pidfile',
                default='/var/run/salt-syndic.pid',
                help=('Specify the location of the pidfile. Default'
                      ' %default'))
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                choices=list(salt.log.LOG_LEVELS),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'warning\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS]))

        options, args = parser.parse_args()

        cli = {'daemon': options.daemon,
               'minion_config': options.minion_config,
               'master_config': options.master_config,
               'pidfile': options.pidfile,
               'user': options.user}

        self.opts = self.__prep_opts(cli)

        if not options.log_level:
            options.log_level = self.opts['log_level']

        salt.log.setup_console_logger(
            options.log_level,
            log_format=self.opts['log_fmt_console'],
            date_format=self.opts['log_datefmt']
        )

        return cli

    def start(self):
        '''
        Execute this method to start up a syndic.
        '''
        try:
            verify_env([
                self.opts['pki_dir'], self.opts['cachedir'],
                os.path.dirname(self.opts['log_file']),
            ], self.opts['user'])
        except OSError, err:
            sys.exit(err.errno)
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].items():
            salt.log.set_logger_level(name, level)

        import logging

        # Late import so logging works correctly
        import salt.minion
        log = logging.getLogger(__name__)
        if self.cli['daemon']:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()
        set_pidfile(self.cli['pidfile'])
        if check_user(self.opts['user'], log):
            try:
                syndic = salt.minion.Syndic(self.opts)
                syndic.tune_in()
            except KeyboardInterrupt:
                log.warn('Stopping the Salt Syndic Minion')
                raise SystemExit('\nExiting on Ctrl-c')
