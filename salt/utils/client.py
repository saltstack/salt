# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2013 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.


    salt.utils.client
    ~~~~~~~~~~~~~~~~~

    Salt clients base class
'''
# pylint: disable=W0212

# Import python libs
import os
import getpass
import logging

# Import salt libs
from salt import config
from salt.log import setup as log
from salt.utils.parsers import is_writeable


class BaseClient(object):

    _client_name_ = None

    _config_filename_ = None

    _default_logging_level_ = 'warning'
    _default_logging_logfile_ = None
    _logfile_config_setting_name_ = 'log_file'
    _loglevel_config_setting_name_ = 'log_level'
    _logfile_loglevel_config_setting_name_ = 'log_level_logfile'
    _skip_console_logging_config_ = True

    def __init__(self, conf_file=None, opts=None, conf_dir=None):
        for setting in ('_client_name_', '_config_filename_',
                        '_default_logging_logfile_'):
            if getattr(self, setting) is None:
                # This is an attribute available for programmers, so, raise a
                # RuntimeError to let them know about the proper usage.
                raise RuntimeError(
                    'Please set {0}.{1}'.format(
                        self.__class__.__name__, setting
                    )
                )

        if not conf_file and not conf_dir and not opts:
            raise RuntimeError(
                'You need to pass at lease one of the following arguments: '
                '`conf_file`, `conf_dir`, `opts`'
            )

        if opts:
            # Store a copy of the loaded options
            self.opts = opts.copy()

            if 'conf_file' not in opts and 'conf_dir' not in opts:
                raise RuntimeError(
                    'You need to define either `conf_file` or `conf_dir` in '
                    'the passed `opts` argument'
                )
            elif 'conf_file' not in opts and 'conf_dir' in opts:
                self.config_dir = opts['config_dir']
                self.config_file = os.path.join(self.config_dir,
                                                self._config_filename_)
            else:
                self.config_file = opts['conf_file']
                self.config_dir = os.path.dirname(self.config_file)
        else:
            self.config_dir = conf_dir or os.path.dirname(conf_file)
            self.config_file = conf_file or os.path.join(
                                                    conf_dir,
                                                    self._config_filename_)
            self.opts = self.load_config()

        # Let's configure the client
        self.__setup_client()

    def load_config(self):
        '''
        This method should return the dictionary of the loaded configuration
        '''
        raise NotImplementedError

    def __setup_client(self):
        self.__setup_console_logger()
        self.__setup_logfile_logger()
        log.setup_extended_logging(self.opts)
        self.setup_client()

    def __setup_console_logger(self):
        if self._skip_console_logging_config_ is True:
            return

        # Since we're not going to be a daemon, setup the console logger
        api_log_fmt = 'api_{0}_log_fmt'.format(self._client_name_)
        if api_log_fmt in self.opts and not self.opts.get(api_log_fmt):
            # Remove it from config so it inherits from log_fmt_console
            self.opts.pop(api_log_fmt)

        logfmt = self.opts.get(
            api_log_fmt, self.opts.get(
                'log_fmt_console',
                self.opts.get(
                    'log_fmt',
                    config._DFLT_LOG_FMT_CONSOLE
                )
            )
        )

        api_log_datefmt = 'api_{0}_log_datefmt'.format(self._client_name_)
        if api_log_datefmt in self.opts and not \
                self.opts.get(api_log_datefmt):
            # Remove it from config so it inherits from log_datefmt_console
            self.opts.pop(api_log_datefmt)

        if self.opts.get('log_datefmt_console', None) is None:
            # Remove it from config so it inherits from log_datefmt
            self.opts.pop('log_datefmt_console', None)

        datefmt = self.opts.get(
            api_log_datefmt,
            self.opts.get(
                'log_datefmt_console',
                self.opts.get(
                    'log_datefmt',
                    '%Y-%m-%d %H:%M:%S'
                )
            )
        )
        log.setup_console_logger(
            self.opts['log_level'], log_format=logfmt, date_format=datefmt
        )
        for name, level in self.opts['log_granular_levels'].items():
            log.set_logger_level(name, level)

    def __setup_logfile_logger(self):
        if self._logfile_loglevel_config_setting_name_ in self.opts and not \
                self.opts.get(self._logfile_loglevel_config_setting_name_):
            # Remove it from config so it inherits from log_level
            self.opts.pop(self._logfile_loglevel_config_setting_name_)

        loglevel = self.opts.get(
            self._logfile_loglevel_config_setting_name_,
            self.opts.get(
                # From the config setting
                self._loglevel_config_setting_name_,
                # From the console setting
                self.opts['log_level']
            )
        )

        api_log_path = 'api_{0}_log_file'.format(self._client_name_)
        if api_log_path in self.opts and not self.opts.get(api_log_path):
            # Remove it from config so it inherits from log_level_logfile
            self.opts.pop(api_log_path)

        if self._logfile_config_setting_name_ in self.opts and not \
                self.opts.get(self._logfile_config_setting_name_):
            # Remove it from config so it inherits from log_file
            self.opts.pop(self._logfile_config_setting_name_)

        logfile = self.opts.get(
            # First from the config cli setting
            api_log_path,
            self.opts.get(
                # From the config setting
                self._logfile_config_setting_name_,
                # From the default setting
                self._default_logging_logfile_
            )
        )

        api_log_file_fmt = 'api_{0}_log_file_fmt'.format(self._client_name_)
        if api_log_file_fmt in self.opts and not \
                self.opts.get(api_log_file_fmt):
            # Remove it from config so it inherits from log_fmt_logfile
            self.opts.pop(api_log_file_fmt)

        if self.opts.get('log_fmt_logfile', None) is None:
            # Remove it from config so it inherits from log_fmt_console
            self.opts.pop('log_fmt_logfile', None)

        log_file_fmt = self.opts.get(
            api_log_file_fmt,
            self.opts.get(
                'api_{0}_log_fmt'.format(self._client_name_),
                self.opts.get(
                    'log_fmt_logfile',
                    self.opts.get(
                        'log_fmt_console',
                        self.opts.get(
                            'log_fmt',
                            config._DFLT_LOG_FMT_CONSOLE
                        )
                    )
                )
            )
        )

        api_log_file_datefmt = 'api_{0}_log_file_datefmt'.format(
            self._client_name_
        )
        if api_log_file_datefmt in self.opts and not \
                self.opts.get(api_log_file_datefmt):
            # Remove it from config so it inherits from log_datefmt_logfile
            self.opts.pop(api_log_file_datefmt)

        if self.opts.get('log_datefmt_logfile', None) is None:
            # Remove it from config so it inherits from log_datefmt_console
            self.opts.pop('log_datefmt_logfile', None)

        if self.opts.get('log_datefmt_console', None) is None:
            # Remove it from config so it inherits from log_datefmt
            self.opts.pop('log_datefmt_console', None)

        log_file_datefmt = self.opts.get(
            api_log_file_datefmt,
            self.opts.get(
                'api_{0}_log_datefmt'.format(self._client_name_),
                self.opts.get(
                    'log_datefmt_logfile',
                    self.opts.get(
                        'log_datefmt_console',
                        self.opts.get(
                            'log_datefmt',
                            '%Y-%m-%d %H:%M:%S'
                        )
                    )
                )
            )
        )

        if not is_writeable(logfile, check_parent=True):
            # Since we're not be able to write to the log file or it's parent
            # directory(if the log file does not exit), are we the same user
            # as the one defined in the configuration file?
            current_user = getpass.getuser()
            if self.opts['user'] != current_user:
                # Yep, not the same user!
                # Is the current user in ACL?
                if current_user in self.opts.get('client_acl', {}).keys():
                    # Yep, the user is in ACL!
                    # Let's write the logfile to it's home directory instead.
                    user_salt_dir = os.path.expanduser('~/.salt')
                    if not os.path.isdir(user_salt_dir):
                        os.makedirs(user_salt_dir, 0750)
                    logfile_basename = os.path.basename(
                        self._default_logging_logfile_
                    )
                    logging.getLogger(__name__).debug(
                        'The user {0!r} is not allowed to write to {1!r}. '
                        'The log file will be stored in '
                        '\'~/.salt/{2!r}.log\''.format(
                            current_user,
                            logfile,
                            logfile_basename
                        )
                    )
                    logfile = os.path.join(
                        user_salt_dir, '{0}.log'.format(logfile_basename)
                    )

            # If we haven't changed the logfile path and it's not writeable,
            # salt will fail once we try to setup the logfile logging.

        log.setup_logfile_logger(
            logfile,
            loglevel,
            log_format=log_file_fmt,
            date_format=log_file_datefmt
        )
        for name, level in self.opts['log_granular_levels'].items():
            log.set_logger_level(name, level)

    def setup_client(self):
        '''
        Override this method for additional client setup
        '''
