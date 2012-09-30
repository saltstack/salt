'''
Make me some salt!
'''

# Import python libs
import os
import sys
import logging
import getpass

# Import salt libs, the try block bypasses an issue at build time so that
# modules don't cause the build to fail
from salt.version import __version__

try:
    import salt.config
    from salt.utils import parsers
    from salt.utils.verify import check_user, verify_env, verify_socket
except ImportError as e:
    if e.args[0] != 'No module named _msgpack':
        raise


class Master(parsers.MasterOptionParser):
    '''
    Creates a master server
    '''

    def start(self):
        '''
        Run the sequence to start a salt master server
        '''
        self.parse_args()

        try:
            if self.config['verify_env']:
                verify_env([
                    self.config['pki_dir'],
                    os.path.join(self.config['pki_dir'], 'minions'),
                    os.path.join(self.config['pki_dir'], 'minions_pre'),
                    os.path.join(self.config['pki_dir'], 'minions_rejected'),
                    self.config['cachedir'],
                    os.path.join(self.config['cachedir'], 'jobs'),
                    os.path.dirname(self.config['log_file']),
                    self.config['sock_dir'],
                ],
                self.config['user'],
                permissive=self.config['permissive_pki_access'],
                pki_dir=self.config['pki_dir'],
                )
        except OSError, err:
            sys.exit(err.errno)

        self.setup_logfile_logger()
        logging.getLogger(__name__).warn('Setting up the Salt Master')

        # Late import so logging works correctly
        if not verify_socket(self.config['interface'],
                             self.config['publish_port'],
                             self.config['ret_port']):
            self.exit(4, 'The ports are not available to bind\n')

        import salt.master
        master = salt.master.Master(self.config)
        self.daemonize_if_required()
        self.set_pidfile()
        if check_user(self.config['user']):
            try:
                master.start()
            except salt.master.MasterExit:
                sys.exit()


class Minion(parsers.MinionOptionParser):
    '''
    Create a minion server
    '''

    def start(self):
        '''
        Execute this method to start up a minion.
        '''
        self.parse_args()

        try:
            if self.config['verify_env']:
                verify_env([
                    self.config['pki_dir'],
                    self.config['cachedir'],
                    self.config['sock_dir'],
                    self.config['extension_modules'],
                    os.path.dirname(self.config['log_file']),
                ],
                self.config['user'],
                permissive=self.config['permissive_pki_access'],
                pki_dir=self.config['pki_dir'],
                )
        except OSError, err:
            sys.exit(err.errno)

        self.setup_logfile_logger()
        logging.getLogger(__name__).warn(
            'Setting up the Salt Minion "{0}"'.format(
                self.config['id']
            )
        )

        # Late import so logging works correctly
        import salt.minion
        # If the minion key has not been accepted, then Salt enters a loop
        # waiting for it, if we daemonize later then the minion could halt
        # the boot process waiting for a key to be accepted on the master.
        # This is the latest safe place to daemonize
        self.daemonize_if_required()
        try:
            minion = salt.minion.Minion(self.config)
            self.set_pidfile()
            if check_user(self.config['user']):
                minion.tune_in()
        except KeyboardInterrupt:
            log.warn('Stopping the Salt Minion')
            raise SystemExit('\nExiting on Ctrl-c')


class Syndic(parsers.SyndicOptionParser):
    '''
    Create a syndic server
    '''

    def start(self):
        '''
        Execute this method to start up a syndic.
        '''
        self.parse_args()
        try:
            if self.config['verify_env']:
                verify_env([
                        self.config['pki_dir'], self.config['cachedir'],
                        os.path.dirname(self.config['log_file']),
                    ],
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )
        except OSError, err:
            sys.exit(err.errno)

        self.setup_logfile_logger()
        logging.getLogger(__name__).warn(
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
                syndic = salt.minion.Syndic(self.config)
                syndic.tune_in()
            except KeyboardInterrupt:
                log.warn('Stopping the Salt Syndic Minion')
                raise SystemExit('\nExiting on Ctrl-c')
