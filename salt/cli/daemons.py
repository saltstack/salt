# coding: utf-8 -*-
'''
Make me some salt!
'''

# Import python libs
from __future__ import absolute_import
import os
import sys
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
from salt.exceptions import SaltSystemExit, SaltClientError, get_error_message


# Let's instantiate logger using salt.log.setup.logging.getLogger() so pylint
# leaves us alone and stops complaining about an un-used import
logger = salt.log.setup.logging.getLogger(__name__)


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
            logger.warning('IMPORTANT: Do not use {h_type} hashing algorithm! Please set "hash_type" to '
                           'sha256 in Salt {d_name} config!'.format(
                h_type=self.config['hash_type'], d_name=self.__class__.__name__))

    def start_log_info(self):
        '''
        Say daemon starting.

        :return:
        '''
        logger.info('The Salt {d_name} is starting up'.format(d_name=self.__class__.__name__))

    def shutdown_log_info(self):
        '''
        Say daemon shutting down.

        :return:
        '''
        logger.info('The Salt {d_name} is shut down'.format(d_name=self.__class__.__name__))

    def environment_failure(self, error):
        '''
        Log environment failure for the daemon and exit with the error code.

        :param error:
        :return:
        '''
        logger.exception('Failed to create environment for {d_name}: {reason}'.format(
            d_name=self.__class__.__name__, reason=get_error_message(error)))
        sys.exit(error.errno)


class Master(parsers.MasterOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Creates a master server
    '''
    def prepare(self):
        '''
        Run the preparation sequence required to start a salt master server.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        self.parse_args()

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
                if logfile is not None and not logfile.startswith(('tcp://',
                                                                   'udp://',
                                                                   'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
                # Clear out syndics from cachedir
                for syndic_file in os.listdir(self.config['syndic_dir']):
                    os.remove(os.path.join(self.config['syndic_dir'], syndic_file))
        except OSError as err:
            self.environment_failure(err)

        self.setup_logfile_logger()
        verify_log(self.config)
        logger.info('Setting up the Salt Master')

        # TODO: AIO core is separate from transport
        if self.config['transport'].lower() in ('zeromq', 'tcp'):
            if not verify_socket(self.config['interface'],
                                 self.config['publish_port'],
                                 self.config['ret_port']):
                self.exit(4, 'The ports are not available to bind\n')
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
        self.prepare()
        if check_user(self.config['user']):
            self.verify_hash_type()
            self.start_log_info()
            self.master.start()

    def shutdown(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
        self.shutdown_log_info()


class Minion(parsers.MinionOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a minion server
    '''
    def prepare(self):
        '''
        Run the preparation sequence required to start a salt minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        self.parse_args()

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
                if logfile is not None and not logfile.startswith(('tcp://',
                                                                'udp://',
                                                                'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
        except OSError as err:
            self.environment_failure(err)

        self.setup_logfile_logger()
        verify_log(self.config)
        logger.info(
            'Setting up the Salt Minion "{0}"'.format(
                self.config['id']
            )
        )
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
        try:
            self.prepare()
            if check_user(self.config['user']):
                self.verify_hash_type()
                self.start_log_info()
                self.minion.tune_in()
                if self.minion.restart:
                    raise SaltClientError('Minion could not connect to Master')
        finally:
            self.shutdown()

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
            logger.warn('Stopping the Salt Minion')
            if isinstance(exc, KeyboardInterrupt):
                logger.warn('Exiting on Ctrl-c')
            else:
                logger.error(str(exc))
        finally:
            self.shutdown()

    def shutdown(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
        self.shutdown_log_info()


class ProxyMinion(parsers.ProxyMinionOptionParser, DaemonsMixin):  # pylint: disable=no-init
    '''
    Create a proxy minion server
    '''

    def prepare(self):
        '''
        Run the preparation sequence required to start a salt minion.

        If sub-classed, don't **ever** forget to run:

            super(YourSubClass, self).prepare()
        '''
        self.parse_args()

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
                if 'proxy_log' in self.config:
                    logfile = self.config['proxy_log']
                else:
                    logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://',
                                                                   'udp://',
                                                                   'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)

        except OSError as err:
            self.environment_failure(err)

        self.setup_logfile_logger()
        verify_log(self.config)
        logger.info(
            'Setting up a Salt Proxy Minion "{0}"'.format(
                self.config['id']
            )
        )
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
        try:
            self.prepare()
            if check_user(self.config['user']):
                self.verify_hash_type()
                self.start_log_info()
                self.minion.tune_in()
        except (KeyboardInterrupt, SaltSystemExit) as exc:
            logger.warn('Stopping the Salt Proxy Minion')
            if isinstance(exc, KeyboardInterrupt):
                logger.warn('Exiting on Ctrl-c')
            else:
                logger.error(str(exc))
        finally:
            self.shutdown()

    def shutdown(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
        if hasattr(self, 'minion') and 'proxymodule' in self.minion.opts:
            proxy_fn = self.minion.opts['proxymodule'].loaded_base_name + '.shutdown'
            self.minion.opts['proxymodule'][proxy_fn](self.minion.opts)
        self.shutdown_log_info()


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
                logfile = self.config['log_file']
                if logfile is not None and not logfile.startswith(('tcp://',
                                                                   'udp://',
                                                                   'file://')):
                    # Logfile is not using Syslog, verify
                    current_umask = os.umask(0o027)
                    verify_files([logfile], self.config['user'])
                    os.umask(current_umask)
        except OSError as err:
            self.environment_failure(err)

        self.setup_logfile_logger()
        verify_log(self.config)
        logger.info(
            'Setting up the Salt Syndic Minion "{0}"'.format(
                self.config['id']
            )
        )

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
        self.prepare()
        if check_user(self.config['user']):
            self.verify_hash_type()
            self.start_log_info()
            try:
                self.syndic.tune_in()
            except KeyboardInterrupt:
                logger.warn('Stopping the Salt Syndic Minion')
                self.shutdown()

    def shutdown(self):
        '''
        If sub-classed, run any shutdown operations on this method.
        '''
        self.shutdown_log_info()
