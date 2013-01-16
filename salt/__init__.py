'''
Make me some salt!
'''

# Import python libs
import os
import sys
import logging

# Import salt libs, the try block bypasses an issue at build time so that
# modules don't cause the build to fail
from salt.version import __version__  # pylint: disable-msg=W402
from salt.utils import migrations

try:
    from salt.utils import parsers
    from salt.utils.verify import check_user, verify_env, verify_socket
    from salt.utils.verify import verify_files
except ImportError as e:
    if e.args[0] != 'No module named _msgpack':
        raise


logger = logging.getLogger(__name__)


class Master(parsers.MasterOptionParser):
    '''
    Creates a master server
    '''

    def run(self):
        '''
        Run the sequence to start a salt master server
        '''
        self.parse_args()

        try:
            if self.config['verify_env']:
                verify_env(
                    [
                        self.config['pki_dir'],
                        os.path.join(self.config['pki_dir'], 'minions'),
                        os.path.join(self.config['pki_dir'], 'minions_pre'),
                        os.path.join(self.config['pki_dir'],
                                     'minions_rejected'),
                        self.config['cachedir'],
                        os.path.join(self.config['cachedir'], 'jobs'),
                        os.path.join(self.config['cachedir'], 'proc'),
                        self.config['sock_dir'],
                        self.config['token_dir'],
                    ],
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )
                if (not self.config['log_file'].startswith('tcp://') or
                    not self.config['log_file'].startswith('udp://') or
                    not self.config['log_file'].startswith('file://')):
                    # Logfile is not using Syslog, verify
                    verify_files(
                        [self.config['log_file']],
                        self.config['user']
                    )
        except OSError as err:
            sys.exit(err.errno)

        self.setup_logfile_logger()
        logger.warn('Setting up the Salt Master')

        if not verify_socket(self.config['interface'],
                             self.config['publish_port'],
                             self.config['ret_port']):
            self.exit(4, 'The ports are not available to bind\n')
        migrations.migrate_paths(self.config)

        # Late import so logging works correctly
        import salt.master
        self.master = salt.master.Master(self.config)
        self.daemonize_if_required()
        self.set_pidfile()
        if check_user(self.config['user']):
            try:
                self.start()
            except salt.master.MasterExit:
                self.stop()
            finally:
                sys.exit()

    def start(self):
        '''
        Start the actual master. If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run your start-up code before calling `super()`.
        '''
        self.master.start()

    def stop(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''


class Minion(parsers.MinionOptionParser):
    '''
    Create a minion server
    '''

    def run(self):
        '''
        Execute this method to start up a minion.
        '''
        self.parse_args()

        try:
            if self.config['verify_env']:
                confd = os.path.join(
                    os.path.dirname(self.config['conf_file']),
                    'minion.d'
                )
                verify_env(
                    [
                        self.config['pki_dir'],
                        self.config['cachedir'],
                        self.config['sock_dir'],
                        self.config['extension_modules'],
                        confd,
                    ],
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )
                if (not self.config['log_file'].startswith('tcp://') or
                    not self.config['log_file'].startswith('udp://') or
                    not self.config['log_file'].startswith('file://')):
                    # Logfile is not using Syslog, verify
                    verify_files(
                        [self.config['log_file']],
                        self.config['user']
                    )
                verify_files(
                    [self.config['log_file']],
                    self.config['user'])
        except OSError as err:
            sys.exit(err.errno)

        self.setup_logfile_logger()
        logger.warn(
            'Setting up the Salt Minion "{0}"'.format(
                self.config['id']
            )
        )
        migrations.migrate_paths(self.config)
        # Late import so logging works correctly
        import salt.minion
        # If the minion key has not been accepted, then Salt enters a loop
        # waiting for it, if we daemonize later then the minion could halt
        # the boot process waiting for a key to be accepted on the master.
        # This is the latest safe place to daemonize
        self.daemonize_if_required()
        try:
            self.minion = salt.minion.Minion(self.config)
            self.set_pidfile()
            if check_user(self.config['user']):
                self.start()
        except KeyboardInterrupt:
            log.warn('Stopping the Salt Minion')
            self.stop()
        finally:
            raise SystemExit('\nExiting on Ctrl-c')

    def start(self):
        '''
        Start the actual minion. If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run your start-up code before calling `super()`.
        '''
        self.minion.tune_in()

    def stop(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''


class Syndic(parsers.SyndicOptionParser):
    '''
    Create a syndic server
    '''

    def run(self):
        '''
        Execute this method to start up a syndic.
        '''
        self.parse_args()
        try:
            if self.config['verify_env']:
                verify_env(
                    [
                        self.config['pki_dir'],
                        self.config['cachedir'],
                        self.config['sock_dir'],
                        self.config['extension_modules'],
                    ],
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )
                if (not self.config['log_file'].startswith('tcp://') or
                    not self.config['log_file'].startswith('udp://') or
                    not self.config['log_file'].startswith('file://')):
                    # Logfile is not using Syslog, verify
                    verify_files(
                        [self.config['log_file']],
                        self.config['user']
                    )
        except OSError as err:
            sys.exit(err.errno)

        self.setup_logfile_logger()
        logger.warn(
            'Setting up the Salt Syndic Minion "{0}"'.format(
                self.config['id']
            )
        )

        # Late import so logging works correctly
        import salt.minion
        self.daemonize_if_required()
        self.set_pidfile()

        if check_user(self.config['user']):
            try:
                self.syndic = salt.minion.Syndic(self.config)
                self.start()
            except KeyboardInterrupt:
                log.warn('Stopping the Salt Syndic Minion')
                self.stop()
            finally:
                raise SystemExit('\nExiting on Ctrl-c')

    def start(self):
        '''
        Start the actual syndic. If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run your start-up code before calling `super()`.
        '''
        self.syndic.tune_in()

    def stop(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
