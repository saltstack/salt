# coding: utf-8 -*-
'''
Make me some salt!
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import warnings
from salt.utils.verify import verify_log


# All salt related deprecation warnings should be shown once each!
warnings.filterwarnings(
    'once',                 # Show once
    '',                     # No deprecation message match
    DeprecationWarning,     # This filter is for DeprecationWarnings
    r'^(salt|salt\.(.*))$'  # Match module(s) 'salt' and 'salt.<whatever>'
)

# While we are supporting Python2.6, hide nested with-statements warnings
warnings.filterwarnings(
    'ignore',
    'With-statements now directly support multiple context managers',
    DeprecationWarning
)

# Filter the backports package UserWarning about being re-imported
warnings.filterwarnings(
    'ignore',
    '^Module backports was already imported from (.*), but (.*) is being added to sys.path$',
    UserWarning
)

# Import salt libs
# We import log ASAP because we NEED to make sure that any logger instance salt
# instantiates is using salt.log.setup.SaltLoggingClass
import salt.log.setup


# the try block below bypasses an issue at build time so that modules don't
# cause the build to fail
from salt.utils import migrations
import salt.utils.kinds as kinds

try:
    from salt.utils.zeromq import ip_bracket
    import salt.utils.parsers
    from salt.utils.verify import check_user, verify_env, verify_socket
except ImportError as exc:
    if exc.args[0] != 'No module named _msgpack':
        raise
from salt.exceptions import SaltSystemExit, SaltClientError, get_error_message


# Let's instantiate log using salt.log.setup.logging.getLogger() so pylint
# leaves us alone and stops complaining about an un-used import
log = salt.log.setup.logging.getLogger(__name__)


class DaemonsMixin(object):  # pylint: disable=no-init
    '''
    Uses the same functions for all daemons
    '''
    def verify_hash_type(self):
        '''
        Verify and display a nag-messsage to the log if vulnerable hash-type is used.

        :return:
        '''
        if self.config['hash_type'].lower() in ['md5', 'sha1']:
            log.warning(
                'IMPORTANT: Do not use %s hashing algorithm! Please set '
                '"hash_type" to sha256 in Salt %s config!',
                self.config['hash_type'], self.__class__.__name__
            )

    def action_log_info(self, action):
        '''
        Say daemon starting.

        :param action
        :return:
        '''
        log.info('%s the Salt %s', action, self.__class__.__name__)

    def start_log_info(self):
        '''
        Say daemon starting.

        :return:
        '''
        log.info('The Salt %s is starting up', self.__class__.__name__)

    def shutdown_log_info(self):
        '''
        Say daemon shutting down.

        :return:
        '''
        log.info('The Salt %s is shut down', self.__class__.__name__)

    def environment_failure(self, error):
        '''
        Log environment failure for the daemon and exit with the error code.

        :param error:
        :return:
        '''
        log.exception(
            'Failed to create environment for %s: %s',
            self.__class__.__name__, get_error_message(error)
        )
        self.shutdown(error)


class Master(salt.utils.parsers.MasterOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Creates a master server
    '''
    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        if hasattr(self.master, 'process_manager'):
            # escalate signal to the process manager processes
            self.master.process_manager.stop_restarting()
            self.master.process_manager.send_signal_to_processes(signum)
            # kill any remaining processes
            self.master.process_manager.kill_children()
        super(Master, self)._handle_signals(signum, sigframe)

    def prepare(self):
        '''
        Run the preparation sequence required to start a salt master server.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        super(Master, self).prepare()

        try:
            if self.config['verify_env']:
                v_dirs = [
                        self.config['pki_dir'],
                        os.path.join(self.config['pki_dir'], 'minions'),
                        os.path.join(self.config['pki_dir'], 'minions_pre'),
                        os.path.join(self.config['pki_dir'], 'minions_denied'),
                        os.path.join(self.config['pki_dir'],
                                     'minions_autosign'),
                        os.path.join(self.config['pki_dir'],
                                     'minions_rejected'),
                        self.config['cachedir'],
                        os.path.join(self.config['cachedir'], 'jobs'),
                        os.path.join(self.config['cachedir'], 'proc'),
                        self.config['sock_dir'],
                        self.config['token_dir'],
                        self.config['syndic_dir'],
                        self.config['sqlite_queue_dir'],
                    ]
                verify_env(
                    v_dirs,
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    root_dir=self.config['root_dir'],
                    pki_dir=self.config['pki_dir'],
                )
                # Clear out syndics from cachedir
                for syndic_file in os.listdir(self.config['syndic_dir']):
                    os.remove(os.path.join(self.config['syndic_dir'], syndic_file))
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        self.action_log_info('Setting up')

        # TODO: AIO core is separate from transport
        if not verify_socket(self.config['interface'],
                             self.config['publish_port'],
                             self.config['ret_port']):
            self.shutdown(4, 'The ports are not available to bind')
        self.config['interface'] = ip_bracket(self.config['interface'])
        migrations.migrate_paths(self.config)

        # Late import so logging works correctly
        import salt.master
        self.master = salt.master.Master(self.config)

        self.daemonize_if_required()
        self.set_pidfile()
        salt.utils.process.notify_systemd()

    def start(self):
        '''
        Start the actual master.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        super(Master, self).start()
        if check_user(self.config['user']):
            self.action_log_info('Starting up')
            self.verify_hash_type()
            self.master.start()

    def shutdown(self, exitcode=0, exitmsg=None):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
        self.shutdown_log_info()
        msg = 'The salt master is shutdown. '
        if exitmsg is not None:
            exitmsg = msg + exitmsg
        else:
            exitmsg = msg.strip()
        super(Master, self).shutdown(exitcode, exitmsg)


class Minion(salt.utils.parsers.MinionOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a minion server
    '''

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate signal to the process manager processes
        if hasattr(self.minion, 'stop'):
            self.minion.stop(signum)
        super(Minion, self)._handle_signals(signum, sigframe)

    # pylint: disable=no-member
    def prepare(self):
        '''
        Run the preparation sequence required to start a salt minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        super(Minion, self).prepare()

        try:
            if self.config['verify_env']:
                confd = self.config.get('default_include')
                if confd:
                    # If 'default_include' is specified in config, then use it
                    if '*' in confd:
                        # Value is of the form "minion.d/*.conf"
                        confd = os.path.dirname(confd)
                    if not os.path.isabs(confd):
                        # If configured 'default_include' is not an absolute
                        # path, consider it relative to folder of 'conf_file'
                        # (/etc/salt by default)
                        confd = os.path.join(
                            os.path.dirname(self.config['conf_file']), confd
                        )
                else:
                    confd = os.path.join(
                        os.path.dirname(self.config['conf_file']), 'minion.d'
                    )

                v_dirs = [
                        self.config['pki_dir'],
                        self.config['cachedir'],
                        self.config['sock_dir'],
                        self.config['extension_modules'],
                        confd,
                    ]

                verify_env(
                    v_dirs,
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    root_dir=self.config['root_dir'],
                    pki_dir=self.config['pki_dir'],
                )
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        log.info('Setting up the Salt Minion "%s"', self.config['id'])
        migrations.migrate_paths(self.config)

        # Bail out if we find a process running and it matches out pidfile
        if self.check_running():
            self.action_log_info('An instance is already running. Exiting')
            self.shutdown(1)

        transport = self.config.get('transport').lower()

        # TODO: AIO core is separate from transport
        if transport in ('zeromq', 'tcp', 'detect'):
            # Late import so logging works correctly
            import salt.minion
            # If the minion key has not been accepted, then Salt enters a loop
            # waiting for it, if we daemonize later then the minion could halt
            # the boot process waiting for a key to be accepted on the master.
            # This is the latest safe place to daemonize
            self.daemonize_if_required()
            self.set_pidfile()
            if self.config.get('master_type') == 'func':
                salt.minion.eval_master_func(self.config)
            self.minion = salt.minion.MinionManager(self.config)
        else:
            log.error(
                'The transport \'%s\' is not supported. Please use one of '
                'the following: tcp, zeromq, or detect.', transport
            )
            self.shutdown(1)

    def start(self):
        '''
        Start the actual minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        super(Minion, self).start()
        while True:
            try:
                self._real_start()
            except SaltClientError as exc:
                # Restart for multi_master failover when daemonized
                if self.options.daemon:
                    continue
            break

    def _real_start(self):
        try:
            if check_user(self.config['user']):
                self.action_log_info('Starting up')
                self.verify_hash_type()
                self.minion.tune_in()
                if self.minion.restart:
                    raise SaltClientError('Minion could not connect to Master')
        except (KeyboardInterrupt, SaltSystemExit) as error:
            self.action_log_info('Stopping')
            if isinstance(error, KeyboardInterrupt):
                log.warning('Exiting on Ctrl-c')
                self.shutdown()
            else:
                log.error(error)
                self.shutdown(error.code)

    def call(self, cleanup_protecteds):
        '''
        Start the actual minion as a caller minion.

        cleanup_protecteds is list of yard host addresses that should not be
        cleaned up this is to fix race condition when salt-caller minion starts up

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        try:
            self.prepare()
            if check_user(self.config['user']):
                self.minion.opts['__role'] = kinds.APPL_KIND_NAMES[kinds.applKinds.caller]
                self.minion.call_in()
        except (KeyboardInterrupt, SaltSystemExit) as exc:
            self.action_log_info('Stopping')
            if isinstance(exc, KeyboardInterrupt):
                log.warning('Exiting on Ctrl-c')
                self.shutdown()
            else:
                log.error(exc)
                self.shutdown(exc.code)

    def shutdown(self, exitcode=0, exitmsg=None):
        '''
        If sub-classed, run any shutdown operations on this method.

        :param exitcode
        :param exitmsg
        '''
        self.action_log_info('Shutting down')
        if hasattr(self, 'minion') and hasattr(self.minion, 'destroy'):
            self.minion.destroy()
        super(Minion, self).shutdown(
            exitcode, ('The Salt {0} is shutdown. {1}'.format(
                self.__class__.__name__, (exitmsg or '')).strip()))
    # pylint: enable=no-member


class ProxyMinion(salt.utils.parsers.ProxyMinionOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a proxy minion server
    '''

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate signal to the process manager processes
        self.minion.stop(signum)
        super(ProxyMinion, self)._handle_signals(signum, sigframe)

    # pylint: disable=no-member
    def prepare(self):
        '''
        Run the preparation sequence required to start a salt proxy minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        super(ProxyMinion, self).prepare()

        if not self.values.proxyid:
            self.error('salt-proxy requires --proxyid')

        # Proxies get their ID from the command line.  This may need to change in
        # the future.
        # We used to set this here.  Now it is set in ProxyMinionOptionParser
        # by passing it via setup_config to config.minion_config
        # self.config['id'] = self.values.proxyid

        try:
            if self.config['verify_env']:
                confd = self.config.get('default_include')
                if confd:
                    # If 'default_include' is specified in config, then use it
                    if '*' in confd:
                        # Value is of the form "minion.d/*.conf"
                        confd = os.path.dirname(confd)
                    if not os.path.isabs(confd):
                        # If configured 'default_include' is not an absolute
                        # path, consider it relative to folder of 'conf_file'
                        # (/etc/salt by default)
                        confd = os.path.join(
                            os.path.dirname(self.config['conf_file']), confd
                        )
                else:
                    confd = os.path.join(
                        os.path.dirname(self.config['conf_file']), 'proxy.d'
                    )

                v_dirs = [
                    self.config['pki_dir'],
                    self.config['cachedir'],
                    self.config['sock_dir'],
                    self.config['extension_modules'],
                    confd,
                ]

                verify_env(
                    v_dirs,
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    root_dir=self.config['root_dir'],
                    pki_dir=self.config['pki_dir'],
                )
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        self.action_log_info('Setting up "{0}"'.format(self.config['id']))

        migrations.migrate_paths(self.config)

        # Bail out if we find a process running and it matches out pidfile
        if self.check_running():
            self.action_log_info('An instance is already running. Exiting')
            self.shutdown(1)

        # TODO: AIO core is separate from transport
        # Late import so logging works correctly
        import salt.minion
        # If the minion key has not been accepted, then Salt enters a loop
        # waiting for it, if we daemonize later then the minion could halt
        # the boot process waiting for a key to be accepted on the master.
        # This is the latest safe place to daemonize
        self.daemonize_if_required()
        self.set_pidfile()
        if self.config.get('master_type') == 'func':
            salt.minion.eval_master_func(self.config)
        self.minion = salt.minion.ProxyMinionManager(self.config)

    def start(self):
        '''
        Start the actual proxy minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        super(ProxyMinion, self).start()
        try:
            if check_user(self.config['user']):
                self.action_log_info('The Proxy Minion is starting up')
                self.verify_hash_type()
                self.minion.tune_in()
                if self.minion.restart:
                    raise SaltClientError('Proxy Minion could not connect to Master')
        except (KeyboardInterrupt, SaltSystemExit) as exc:
            self.action_log_info('Proxy Minion Stopping')
            if isinstance(exc, KeyboardInterrupt):
                log.warning('Exiting on Ctrl-c')
                self.shutdown()
            else:
                log.error(exc)
                self.shutdown(exc.code)

    def shutdown(self, exitcode=0, exitmsg=None):
        '''
        If sub-classed, run any shutdown operations on this method.

        :param exitcode
        :param exitmsg
        '''
        if hasattr(self, 'minion') and 'proxymodule' in self.minion.opts:
            proxy_fn = self.minion.opts['proxymodule'].loaded_base_name + '.shutdown'
            self.minion.opts['proxymodule'][proxy_fn](self.minion.opts)
        self.action_log_info('Shutting down')
        super(ProxyMinion, self).shutdown(
            exitcode, ('The Salt {0} is shutdown. {1}'.format(
                self.__class__.__name__, (exitmsg or '')).strip()))
    # pylint: enable=no-member


class Syndic(salt.utils.parsers.SyndicOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a syndic server
    '''

    def prepare(self):
        '''
        Run the preparation sequence required to start a salt syndic minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        super(Syndic, self).prepare()
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
                    root_dir=self.config['root_dir'],
                    pki_dir=self.config['pki_dir'],
                )
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        self.action_log_info('Setting up "{0}"'.format(self.config['id']))

        # Late import so logging works correctly
        import salt.minion
        self.daemonize_if_required()
        self.syndic = salt.minion.SyndicManager(self.config)
        self.set_pidfile()

    def start(self):
        '''
        Start the actual syndic.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        super(Syndic, self).start()
        if check_user(self.config['user']):
            self.action_log_info('Starting up')
            self.verify_hash_type()
            try:
                self.syndic.tune_in()
            except KeyboardInterrupt:
                self.action_log_info('Stopping')
                self.shutdown()

    def shutdown(self, exitcode=0, exitmsg=None):
        '''
        If sub-classed, run any shutdown operations on this method.

        :param exitcode
        :param exitmsg
        '''
        self.action_log_info('Shutting down')
        super(Syndic, self).shutdown(
            exitcode, ('The Salt {0} is shutdown. {1}'.format(
                self.__class__.__name__, (exitmsg or '')).strip()))
