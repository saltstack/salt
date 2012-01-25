'''
Make me some salt!
'''
from salt.version import __version__

# Import python libs
import os
import sys
import stat
import optparse
import getpass

# Import salt libs, the try block bypasses an issue at build time so that c
# modules don't cause the build to fail
try:
    import salt.config
    import salt.utils.verify
except ImportError as e:
    if e.message != 'No module named _msgpack':
        raise


def set_pidfile(pidfile):
    '''
    Save the pidfile
    '''
    pdir = os.path.dirname(pidfile)
    if not os.path.isdir(pdir):
        os.makedirs(pdir)
    try:
        open(pidfile, 'w+').write(str(os.getpid()))
    except IOError:
        err = ('Failed to commit the pid file to location {0}, please verify'
              ' that the location is available').format(pidfile)


def verify_env(dirs):
    '''
    Verify that the named directories are in place and that the environment
    can shake the salt
    '''
    for dir_ in dirs:
        if not os.path.isdir(dir_):
            try:
                cumask = os.umask(63)  # 077
                os.makedirs(dir_)
                os.umask(cumask)
            except OSError, e:
                sys.stderr.write('Failed to create directory path "{0}" - {1}\n'.format(dir_, e))

        mode = os.stat(dir_)
        # TODO: Should this log if it can't set the permissions
        #       to very secure for these PKI cert  directories?
        if not stat.S_IMODE(mode.st_mode) == 448:
            if os.access(dir_, os.W_OK):
                os.chmod(dir_, 448)
    # Run the extra verification checks
    salt.utils.verify.run()


def check_user(user, log):
    '''
    Check user and assign process uid/gid.
    '''
    if 'os' in os.environ:
        if os.environ['os'].startswith('Windows'):
            return True
    if user == getpass.getuser():
        return True
    import pwd  # after confirming not running Windows
    try:
        p = pwd.getpwnam(user)
        try:
            os.setgid(p.pw_gid)
            os.setuid(p.pw_uid)
        except OSError:
            if user == 'root':
                msg = 'Sorry, the salt must run as root.  http://xkcd.com/838'
            else:
                msg = 'Salt must be run from root or user "{0}"'.format(user)
            log.critical(msg)
            return False
    except KeyError:
        msg = 'User not found: "{0}"'.format(user)
        log.critical(msg)
        return False
    return True

class Master(object):
    '''
    Creates a master server
    '''
    def __init__(self):
        self.cli = self.__parse_cli()
        self.opts = salt.config.master_config(self.cli['config'])
        # command line overrides config
        if self.cli['user']:
            self.opts['user'] = self.cli['user']

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
                help='Run the master in a daemon')
        parser.add_option('-c',
                '--config',
                dest='config',
                default='/etc/salt/master',
                help='Pass in an alternative configuration file')
        parser.add_option('-u',
                '--user',
                dest='user',
                help='Specify user to run minion')
        parser.add_option('--pid-file',
                dest='pidfile',
                default='/var/run/salt-master.pid',
                help=('Specify the location of the pidfile, default is'
                      ' /var/run/salt-master.pid'))
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                default='warning',
                choices=salt.log.LOG_LEVELS.keys(),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'%%default\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS.keys()])
                )
        log_format = '%(asctime)s,%(msecs)03.0f [%(name)-15s][%(levelname)-8s] %(message)s'
        options, args = parser.parse_args()
        salt.log.setup_console_logger(options.log_level, log_format=log_format)

        cli = {'daemon': options.daemon,
               'config': options.config,
               'user': options.user,
               'pidfile': options.pidfile}

        return cli

    def start(self):
        '''
        Run the sequence to start a salt master server
        '''
        verify_env([os.path.join(self.opts['pki_dir'], 'minions'),
                    os.path.join(self.opts['pki_dir'], 'minions_pre'),
                    os.path.join(self.opts['pki_dir'], 'minions_rejected'),
                    os.path.join(self.opts['cachedir'], 'jobs'),
                    os.path.dirname(self.opts['log_file']),
                    self.opts['sock_dir'],
                    ])
        set_pidfile(cli['pidfile'])
        import salt.log
        salt.log.setup_logfile_logger(
            self.opts['log_file'], self.opts['log_level']
        )
        for name, level in self.opts['log_granular_levels'].iteritems():
            salt.log.set_logger_level(name, level)
        import logging
        log = logging.getLogger(__name__)
        # Late import so logging works correctly
        if check_user(self.opts['user'], log):
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
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                default='warning',
                choices=salt.log.LOG_LEVELS.keys(),
                help='Console log level. One of %s. For the logfile settings '
                     'see the config file. Default: \'%%default\'.' %
                     ', '.join([repr(l) for l in salt.log.LOG_LEVELS.keys()]))

        options, args = parser.parse_args()
        log_format = '%(asctime)s,%(msecs)03.0f [%(name)-15s][%(levelname)-8s] %(message)s'
        salt.log.setup_console_logger(options.log_level, log_format=log_format)
        cli = {'daemon': options.daemon,
               'config': options.config,
               'user': options.user}

        return cli

    def start(self):
        '''
        Execute this method to start up a minion.
        '''
        verify_env([self.opts['pki_dir'],
            self.opts['cachedir'],
            self.opts['extension_modules'],
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
        log = logging.getLogger(__name__)
        if check_user(self.opts['user'], log):
            try:
                if self.cli['daemon']:
                    # Late import so logging works correctly
                    import salt.utils
                    salt.utils.daemonize()
                minion = salt.minion.Minion(self.opts)
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
        self.opts = self.__prep_opts()
        # command line overrides config
        if self.cli['user']:
            self.opts['user'] = self.cli['user']

    def __prep_opts(self):
        '''
        Generate the opts used by the syndic
        '''
        opts = salt.config.master_config(self.cli['master_config'])
        opts['_minion_conf_file'] = opts['conf_file']
        opts.update(salt.config.minion_config(self.cli['minion_config']))
        if 'syndic_master' in opts:
            # Some of the opts need to be changed to match the needed opts
            # in the minion class.
            opts['master'] = opts['syndic_master']
            opts['master_ip'] = salt.config.dns_check(opts['master'])

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
        Parse the cli for options passed to a master daemon
        '''
        import salt.log
        parser = optparse.OptionParser(version="%%prog %s" % __version__)
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
        parser.add_option('-u',
                '--user',
                dest='user',
                help='Specify user to run minion')
        parser.add_option('-l',
                '--log-level',
                dest='log_level',
                default='warning',
                choices=salt.log.LOG_LEVELS.keys(),
                help=('Console log level. One of %s. For the logfile settings '
                      'see the config file. Default: \'%%default\'.' %
                      ', '.join([repr(l) for l in salt.log.LOG_LEVELS.keys()]))
                     )

        options, args = parser.parse_args()
        salt.log.setup_console_logger(options.log_level)

        cli = {'daemon': options.daemon,
               'minion_config': options.minion_config,
               'master_config': options.master_config,
               'user': options.user}

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
        log = logging.getLogger(__name__)
        if check_user(self.opts['user'], log):
            try:
                syndic = salt.minion.Syndic(self.opts)
                if self.cli['daemon']:
                    # Late import so logging works correctly
                    import salt.utils
                    salt.utils.daemonize()
                syndic.tune_in()
            except KeyboardInterrupt:
                log.warn('Stopping the Salt Syndic Minion')
                raise SystemExit('\nExiting on Ctrl-c')
