# coding: utf-8 -*-
'''
Make me some salt!
'''

# Import python libs
from __future__ import absolute_import
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
from salt.utils import kinds

try:
    from salt.utils import parsers, ip_bracket
    from salt.utils.verify import check_user, verify_env, verify_socket
    from salt.utils.verify import verify_files
except ImportError as exc:
    if exc.args[0] != 'No module named _msgpack':
        raise
from salt.exceptions import SaltSystemExit


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
            log.warning('IMPORTANT: Do not use {h_type} hashing algorithm! Please set "hash_type" to '
                        'SHA256 in Salt {d_name} config!'.format(
                        h_type=self.config['hash_type'], d_name=self.__class__.__name__))

    def action_log_info(self, action):
        '''
        Say daemon starting.

        :param action
        :return:
        '''
        log.info('{action} the Salt {d_name}'.format(d_name=self.__class__.__name__, action=action))

    def start_log_info(self):
        '''
        Say daemon starting.

        :return:
        '''
        log.info('The Salt {d_name} is starting up'.format(d_name=self.__class__.__name__))

    def shutdown_log_info(self):
        '''
        Say daemon shutting down.

        :return:
        '''
        log.info('The Salt {d_name} is shut down'.format(d_name=self.__class__.__name__))

    def environment_failure(self, error):
        '''
        Log environment failure for the daemon and exit with the error code.

        :param error:
        :return:
        '''
        log.exception('Failed to create environment for {d_name}: {reason}'.format(
            d_name=self.__class__.__name__, reason=error.message))
        self.shutdown(error)


class Master(parsers.MasterOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Creates a master server
    '''
    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
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
                if self.config.get('transport') == 'raet':
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'accepted'))
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'pending'))
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'rejected'))
                    v_dirs.append(os.path.join(self.config['cachedir'], 'raet'))
                verify_env(
                    v_dirs,
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://', 'udp://', 'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
                # Clear out syndics from cachedir
                for syndic_file in os.listdir(self.config['syndic_dir']):
                    os.remove(os.path.join(self.config['syndic_dir'], syndic_file))
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        self.action_log_info('Setting up')

        # TODO: AIO core is separate from transport
        if self.config['transport'].lower() in ('zeromq', 'tcp'):
            if not verify_socket(self.config['interface'],
                                 self.config['publish_port'],
                                 self.config['ret_port']):
                self.shutdown(4, 'The ports are not available to bind')
            self.config['interface'] = ip_bracket(self.config['interface'])
            migrations.migrate_paths(self.config)

            # Late import so logging works correctly
            import salt.master
            self.master = salt.master.Master(self.config)
        else:
            # Add a udp port check here
            import salt.daemons.flo
            self.master = salt.daemons.flo.IofloMaster(self.config)
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


class Minion(parsers.MinionOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a minion server
    '''

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        # escalate signal to the process manager processes
        self.minion.process_manager.stop_restarting()
        self.minion.process_manager.send_signal_to_processes(signum)
        # kill any remaining processes
        self.minion.process_manager.kill_children()
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

                if self.config.get('transport') == 'raet':
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'accepted'))
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'pending'))
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'rejected'))
                    v_dirs.append(os.path.join(self.config['cachedir'], 'raet'))

                verify_env(
                    v_dirs,
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://', 'udp://', 'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        log.info(
            'Setting up the Salt Minion "{0}"'.format(
                self.config['id']
            )
        )
        migrations.migrate_paths(self.config)

        # Bail out if we find a process running and it matches out pidfile
        if self.check_running():
            self.action_log_info('An instance is already running. Exiting')
            self.shutdown(1)

        # TODO: AIO core is separate from transport
        if self.config['transport'].lower() in ('zeromq', 'tcp'):
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
            if isinstance(self.config.get('master'), list):
                if self.config.get('master_type') == 'failover':
                    self.minion = salt.minion.Minion(self.config)
                else:
                    self.minion = salt.minion.MultiMinion(self.config)
            else:
                self.minion = salt.minion.Minion(self.config)
        else:
            import salt.daemons.flo
            self.daemonize_if_required()
            self.set_pidfile()
            self.minion = salt.daemons.flo.IofloMinion(self.config)

    def start(self):
        '''
        Start the actual minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).start()

        NOTE: Run any required code before calling `super()`.
        '''
        super(Minion, self).start()
        try:
            if check_user(self.config['user']):
                self.action_log_info('Starting up')
                self.verify_hash_type()
                self.minion.tune_in()
        except (KeyboardInterrupt, SaltSystemExit) as error:
            self.action_log_info('Stopping')
            if isinstance(error, KeyboardInterrupt):
                log.warning('Exiting on Ctrl-c')
                self.shutdown()
            else:
                log.error(str(error))
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
                self.minion.opts['raet_cleanup_protecteds'] = cleanup_protecteds
                self.minion.call_in()
        except (KeyboardInterrupt, SaltSystemExit) as exc:
            self.action_log_info('Stopping')
            if isinstance(exc, KeyboardInterrupt):
                log.warning('Exiting on Ctrl-c')
                self.shutdown()
            else:
                log.error(str(exc))
                self.shutdown(exc.code)

    def shutdown(self, exitcode=0, exitmsg=None):
        '''
        If sub-classed, run any shutdown operations on this method.

        :param exitcode
        :param exitmsg
        '''
        self.action_log_info('Shutting down')
        if hasattr(self, 'minion'):
            self.minion.destroy()
        super(Minion, self).shutdown(
            exitcode, ('The Salt {0} is shutdown. {1}'.format(
                self.__class__.__name__, (exitmsg or '')).strip()))
    # pylint: enable=no-member


class ProxyMinion(parsers.ProxyMinionOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a proxy minion server
    '''

    # pylint: disable=no-member
    def prepare(self):
        '''
        Run the preparation sequence required to start a salt minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        super(ProxyMinion, self).prepare()

        if not self.values.proxyid:
            raise SaltSystemExit('salt-proxy requires --proxyid')

        # Proxies get their ID from the command line.  This may need to change in
        # the future.
        self.config['id'] = self.values.proxyid

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

                if self.config.get('transport') == 'raet':
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'accepted'))
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'pending'))
                    v_dirs.append(os.path.join(self.config['pki_dir'], 'rejected'))
                    v_dirs.append(os.path.join(self.config['cachedir'], 'raet'))

                verify_env(
                    v_dirs,
                    self.config['user'],
                    permissive=self.config['permissive_pki_access'],
                    pki_dir=self.config['pki_dir'],
                )

                logfile = self.config.get('proxy_log') or self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://', 'udp://', 'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)

        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        self.action_log_info('Setting up "{0}"'.format(self.config['id']))

        migrations.migrate_paths(self.config)
        # TODO: AIO core is separate from transport
        if self.config['transport'].lower() in ('zeromq', 'tcp'):
            # Late import so logging works correctly
            import salt.minion
            # If the minion key has not been accepted, then Salt enters a loop
            # waiting for it, if we daemonize later then the minion could halt
            # the boot process waiting for a key to be accepted on the master.
            # This is the latest safe place to daemonize
            self.daemonize_if_required()
            self.set_pidfile()
            # TODO Proxy minions don't currently support failover
            self.minion = salt.minion.ProxyMinion(self.config)
        else:
            # For proxy minions, this doesn't work yet.
            import salt.daemons.flo
            self.daemonize_if_required()
            self.set_pidfile()
            self.minion = salt.daemons.flo.IofloMinion(self.config)

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
                log.info('The proxy minion is starting up')
                self.verify_hash_type()
                self.action_log_info('Starting up')
                self.minion.tune_in()
        except (KeyboardInterrupt, SaltSystemExit) as exc:
            self.action_log_info('Stopping')
            if isinstance(exc, KeyboardInterrupt):
                log.warning('Exiting on Ctrl-c')
                self.shutdown()
            else:
                log.error(str(exc))
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


class Syndic(parsers.SyndicOptionParser, DaemonsMixin):  # pylint: disable=no-init
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
                    pki_dir=self.config['pki_dir'],
                )
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://', 'udp://', 'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
        except OSError as error:
            self.environment_failure(error)

        self.setup_logfile_logger()
        verify_log(self.config)
        self.action_log_info('Setting up "{0}"'.format(self.config['id']))

        # Late import so logging works correctly
        import salt.minion
        self.daemonize_if_required()
        # if its a multisyndic, do so
        if isinstance(self.config.get('master'), list):
            self.syndic = salt.minion.MultiSyndic(self.config)
        else:
            self.syndic = salt.minion.Syndic(self.config)
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
