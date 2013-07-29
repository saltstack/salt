# -*- coding: utf-8 -*-
'''
    salt.utils.parsers
    ~~~~~~~~~~~~~~~~~~

    This is were all the black magic happens on all of salt's CLI tools.

    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`
    :copyright: © 2012 by the SaltStack Team, see AUTHORS for more details.
    :license: Apache 2.0, see LICENSE for more details.
'''

# Import python libs
import os
import sys
import logging
import optparse
import warnings
import traceback
from functools import partial

# Import salt libs
import salt.log as log
import salt.config as config
import salt.loader as loader
import salt.utils as utils
import salt.version as version


def _sorted(mixins_or_funcs):
    return sorted(
        mixins_or_funcs, key=lambda mf: getattr(mf, '_mixin_prio_', 1000)
    )


class MixInMeta(type):
    # This attribute here won't actually do anything. But, if you need to
    # specify an order or a dependency within the mix-ins, please define the
    # attribute on your own MixIn
    _mixin_prio_ = 0

    def __new__(mcs, name, bases, attrs):
        instance = super(MixInMeta, mcs).__new__(mcs, name, bases, attrs)
        if not hasattr(instance, '_mixin_setup'):
            raise RuntimeError(
                'Don\'t subclass {0} in {1} if you\'re not going to use it '
                'as a salt parser mix-in.'.format(mcs.__name__, name)
            )
        return instance


class OptionParserMeta(MixInMeta):
    def __new__(mcs, name, bases, attrs):
        instance = super(OptionParserMeta, mcs).__new__(mcs,
                                                        name,
                                                        bases,
                                                        attrs)
        if not hasattr(instance, '_mixin_setup_funcs'):
            instance._mixin_setup_funcs = []
        if not hasattr(instance, '_mixin_process_funcs'):
            instance._mixin_process_funcs = []
        if not hasattr(instance, '_mixin_after_parsed_funcs'):
            instance._mixin_after_parsed_funcs = []

        for base in _sorted(bases + (instance,)):
            func = getattr(base, '_mixin_setup', None)
            if func is not None and func not in instance._mixin_setup_funcs:
                instance._mixin_setup_funcs.append(func)

            func = getattr(base, '_mixin_after_parsed', None)
            if func is not None and func not in \
                    instance._mixin_after_parsed_funcs:
                instance._mixin_after_parsed_funcs.append(func)

            # Mark process_<opt> functions with the base priority for sorting
            for func in dir(base):
                if not func.startswith('process_'):
                    continue

                func = getattr(base, func)
                if getattr(func, '_mixin_prio_', None) is not None:
                    # Function already has the attribute set, don't override it
                    continue

                func.__func__._mixin_prio_ = getattr(
                    base, '_mixin_prio_', 1000
                )

        return instance


class OptionParser(optparse.OptionParser):
    VERSION = version.__version__

    usage = '%prog'

    epilog = ('You can find additional help about %prog issuing "man %prog" '
              'or on http://docs.saltstack.org')
    description = None

    # Private attributes
    _mixin_prio_ = 100

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('version', '%prog {0}'.format(self.VERSION))
        kwargs.setdefault('usage', self.usage)
        if self.description:
            kwargs.setdefault('description', self.description)

        if self.epilog:
            kwargs.setdefault('epilog', self.epilog)

        optparse.OptionParser.__init__(self, *args, **kwargs)

        if self.epilog and '%prog' in self.epilog:
            self.epilog = self.epilog.replace('%prog', self.get_prog_name())

    def parse_args(self, args=None, values=None):
        options, args = optparse.OptionParser.parse_args(self, args, values)
        if options.versions_report:
            self.print_versions_report()

        self.options, self.args = options, args

        # Let's get some proper sys.stderr logging as soon as possible!!!
        # This logging handler will be removed once the proper console or
        # logfile logging is setup.
        log.setup_temp_logger(
            getattr(self.options, 'log_level', 'error')
        )

        # Gather and run the process_<option> functions in the proper order
        process_option_funcs = []
        for option_key in options.__dict__.keys():
            process_option_func = getattr(
                self, 'process_{0}'.format(option_key), None
            )
            if process_option_func is not None:
                process_option_funcs.append(process_option_func)

        for process_option_func in _sorted(process_option_funcs):
            try:
                process_option_func()
            except Exception as err:
                logging.getLogger(__name__).exception(err)
                self.error(
                    'Error while processing {0}: {1}'.format(
                        process_option_func, traceback.format_exc(err)
                    )
                )

        # Run the functions on self._mixin_after_parsed_funcs
        for mixin_after_parsed_func in self._mixin_after_parsed_funcs:
            try:
                mixin_after_parsed_func(self)
            except Exception as err:
                logging.getLogger(__name__).exception(err)
                self.error(
                    'Error while processing {0}: {1}'.format(
                        mixin_after_parsed_func, traceback.format_exc(err)
                    )
                )

        if self.config.get('conf_file', None) is not None:
            logging.getLogger(__name__).debug(
                'Configuration file path: {0}'.format(
                    self.config['conf_file']
                )
            )
        # Retain the standard behaviour of optparse to return options and args
        return options, args

    def _populate_option_list(self, option_list, add_help=True):
        optparse.OptionParser._populate_option_list(
            self, option_list, add_help=add_help
        )
        for mixin_setup_func in self._mixin_setup_funcs:
            mixin_setup_func(self)

    def _add_version_option(self):
        optparse.OptionParser._add_version_option(self)
        self.add_option(
            '--versions-report', action='store_true',
            help='show program\'s dependencies version number and exit'
        )

    def print_versions_report(self, file=sys.stdout):
        print >> file, '\n'.join(version.versions_report())
        self.exit()


class MergeConfigMixIn(object):
    '''
    This mix-in will simply merge the CLI-passed options, by overriding the
    configuration file loaded settings.

    This mix-in should run last.
    '''
    __metaclass__ = MixInMeta
    _mixin_prio_ = sys.maxint

    def _mixin_setup(self):
        if not hasattr(self, 'setup_config') and not hasattr(self, 'config'):
            # No configuration was loaded on this parser.
            # There's nothing to do here.
            return

        # Add an additional function that will merge the shell options with
        # the config options and if needed override them
        self._mixin_after_parsed_funcs.append(self.__merge_config_with_cli)

    def __merge_config_with_cli(self, *args):
        # Merge parser options
        for option in self.option_list:
            if option.dest is None:
                # --version does not have dest attribute set for example.
                # All options defined by us, even if not explicitly(by kwarg),
                # will have the dest attribute set
                continue

            # Get the passed value from shell. If empty get the default one
            default = self.defaults.get(option.dest)
            value = getattr(self.options, option.dest, default)

            if option.dest not in self.config:
                # There's no value in the configuration file
                if value is not None:
                    # There's an actual value, add it to the config
                    self.config[option.dest] = value
            elif value is not None and value != default:
                # Only set the value in the config file IF it's not the default
                # value, this allows to tweak settings on the configuration
                # files bypassing the shell option flags
                self.config[option.dest] = value

        # Merge parser group options if any
        for group in self.option_groups:
            for option in group.option_list:
                if option.dest is None:
                    continue
                # Get the passed value from shell. If empty get the default one
                default = self.defaults.get(option.dest)
                value = getattr(self.options, option.dest, default)
                if option.dest not in self.config:
                    # There's no value in the configuration file
                    if value is not None:
                        # There's an actual value, add it to the config
                        self.config[option.dest] = value
                else:
                    if value is not None and value != default:
                        # Only set the value in the config file IF it's not the
                        # default value, this allows to tweak settings on the
                        # configuration files bypassing the shell option flags
                        self.config[option.dest] = value


class ConfigDirMixIn(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = -10
    _config_filename_ = None

    def _mixin_setup(self):
        default = '/etc/salt'
        if utils.is_windows():
            default = 'c:\\salt\\conf'
        self.add_option(
            '-c', '--config-dir', default=default,
            help=('Pass in an alternative configuration directory. Default: '
                  '%default')
        )

    def process_config_dir(self):
        if not os.path.isdir(self.options.config_dir):
            # No logging is configured yet
            sys.stderr.write(
                'WARNING: "{0}" directory does not exist.\n'.format(
                    self.options.config_dir
                )
            )

        # Make sure we have an absolute path
        self.options.config_dir = os.path.abspath(self.options.config_dir)

        if hasattr(self, 'setup_config'):
            self.config = self.setup_config()

    def get_config_file_path(self, configfile=None):
        if configfile is None:
            configfile = self._config_filename_
        return os.path.join(self.options.config_dir, configfile)


class LogLevelMixIn(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 10
    _default_logging_level_ = 'warning'
    _default_logging_logfile_ = None
    _logfile_config_setting_name_ = 'log_file'
    _loglevel_config_setting_name_ = 'log_level_logfile'
    _skip_console_logging_config_ = False

    def _mixin_setup(self):
        if self._default_logging_logfile_ is None:
            # This is an attribute available for programmers, so, raise a
            # RuntimeError to let them know about the proper usage.
            raise RuntimeError(
                'Please set {0}._default_logging_logfile_'.format(
                    self.__class__.__name__
                )
            )
        group = self.logging_options_group = optparse.OptionGroup(
            self, 'Logging Options',
            'Logging options which override any settings defined on the '
            'configuration files.'
        )
        self.add_option_group(group)

        if not getattr(self, '_skip_console_logging_config_', False):
            group.add_option(
                '-l', '--log-level',
                choices=list(log.LOG_LEVELS),
                help='Console logging log level. One of {0}. '
                     'Default: \'{1}\'.'.format(
                         ', '.join([repr(l) for l in log.SORTED_LEVEL_NAMES]),
                         getattr(self, '_default_logging_level_', 'warning')
                     )
            )

        group.add_option(
            '--log-file',
            default=None,
            help='Log file path. Default: {0}.'.format(
                self._default_logging_logfile_
            )
        )

        group.add_option(
            '--log-file-level',
            dest=self._loglevel_config_setting_name_,
            choices=list(log.LOG_LEVELS),
            help='Logfile logging log level. One of {0}. '
                 'Default: \'{1}\'.'.format(
                     ', '.join([repr(l) for l in log.SORTED_LEVEL_NAMES]),
                     getattr(self, '_default_logging_level_', 'warning')
                 )
        )

    def process_log_level(self):
        if not self.options.log_level:
            cli_log_level = 'cli_{0}_log_level'.format(
                self.get_prog_name().replace('-', '_')
            )
            if self.config.get(cli_log_level, None) is not None:
                self.options.log_level = self.config.get(cli_log_level)
            elif self.config.get('log_level', None) is not None:
                self.options.log_level = self.config.get('log_level')
            else:
                self.options.log_level = self._default_logging_level_
        # Setup the console as the last _mixin_after_parsed_func to run
        self._mixin_after_parsed_funcs.append(self.__setup_console_logger)

    def process_log_file(self):
        if not self.options.log_file:
            cli_setting_name = 'cli_{0}_log_file'.format(
                self.get_prog_name().replace('-', '_')
            )
            if self.config.get(cli_setting_name, None) is not None:
                # There's a configuration setting defining this log file path,
                # ie, `key_log_file` if the cli tool is `salt-key`
                self.options.log_file = self.config.get(cli_setting_name)
            elif self.config.get(self._logfile_config_setting_name_, None):
                # Is the regular log file setting set?
                self.options.log_file = self.config.get(
                    self._logfile_config_setting_name_
                )
            else:
                # Nothing is set on the configuration? Let's use the cli tool
                # defined default
                self.options.log_file = self._default_logging_logfile_

    def process_log_file_level(self):
        if not self.options.log_file_level:
            cli_setting_name = 'cli_{0}_log_file_level'.format(
                self.get_prog_name().replace('-', '_')
            )
            if self.config.get(cli_setting_name, None) is not None:
                # There's a configuration setting defining this log file
                # logging level, ie, `key_log_file_level` if the cli tool is
                # `salt-key`
                self.options.log_file_level = self.config.get(cli_setting_name)
            elif self.config.get(self._loglevel_config_setting_name_, None):
                # Is the regular log file level setting set?
                self.options.log_file_level = self.config.get(
                    self._loglevel_config_setting_name_
                )
            else:
                # Nothing is set on the configuration? Let's use the cli tool
                # defined default
                self.options.log_level = self._default_logging_level_

    def setup_logfile_logger(self):
        if self._loglevel_config_setting_name_ in self.config and not \
                self.config.get(self._loglevel_config_setting_name_):
            # Remove it from config so it inherits from log_level
            self.config.pop(self._loglevel_config_setting_name_)

        loglevel = self.config.get(
            self._loglevel_config_setting_name_,
            self.config.get(
                # From the config setting
                'log_level_logfile',
                # From the console setting
                self.config['log_level']
            )
        )

        cli_log_path = 'cli_{0}_log_file'.format(
            self.get_prog_name().replace('-', '_')
        )
        if cli_log_path in self.config and not self.config.get(cli_log_path):
            # Remove it from config so it inherits from log_level_logfile
            self.config.pop(cli_log_path)

        if self._logfile_config_setting_name_ in self.config and not \
                self.config.get(self._logfile_config_setting_name_):
            # Remove it from config so it inherits from log_file
            self.config.pop(self._logfile_config_setting_name_)

        logfile = self.config.get(
            # First from the config cli setting
            cli_log_path,
            self.config.get(
                # From the config setting
                self._logfile_config_setting_name_,
                # From the default setting
                self._default_logging_logfile_
            )
        )

        cli_log_file_fmt = 'cli_{0}_log_file_fmt'.format(
            self.get_prog_name().replace('-', '_')
        )
        if cli_log_file_fmt in self.config and not \
                self.config.get(cli_log_file_fmt):
            # Remove it from config so it inherits from log_fmt_logfile
            self.config.pop(cli_log_file_fmt)

        if self.config.get('log_fmt_logfile', None) is None:
            # Remove it from config so it inherits from log_fmt_console
            self.config.pop('log_fmt_logfile', None)

        log_file_fmt = self.config.get(
            cli_log_file_fmt,
            self.config.get(
                'cli_{0}_log_fmt'.format(
                    self.get_prog_name().replace('-', '_')
                ),
                self.config.get(
                    'log_fmt_logfile',
                    self.config.get(
                        'log_fmt_console',
                        self.config.get(
                            'log_fmt',
                            config._DFLT_LOG_FMT_CONSOLE
                        )
                    )
                )
            )
        )

        cli_log_file_datefmt = 'cli_{0}_log_file_datefmt'.format(
            self.get_prog_name().replace('-', '_')
        )
        if cli_log_file_datefmt in self.config and not \
                self.config.get(cli_log_file_datefmt):
            # Remove it from config so it inherits from log_datefmt_logfile
            self.config.pop(cli_log_file_datefmt)

        if self.config.get('log_datefmt_logfile', None) is None:
            # Remove it from config so it inherits from log_datefmt_console
            self.config.pop('log_datefmt_logfile', None)

        if self.config.get('log_datefmt_console', None) is None:
            # Remove it from config so it inherits from log_datefmt
            self.config.pop('log_datefmt_console', None)

        log_file_datefmt = self.config.get(
            cli_log_file_datefmt,
            self.config.get(
                'cli_{0}_log_datefmt'.format(
                    self.get_prog_name().replace('-', '_')
                ),
                self.config.get(
                    'log_datefmt_logfile',
                    self.config.get(
                        'log_datefmt_console',
                        self.config.get(
                            'log_datefmt',
                            '%Y-%m-%d %H:%M:%S'
                        )
                    )
                )
            )
        )

        log.setup_logfile_logger(
            logfile,
            loglevel,
            log_format=log_file_fmt,
            date_format=log_file_datefmt
        )
        for name, level in self.config['log_granular_levels'].items():
            log.set_logger_level(name, level)

    def __setup_console_logger(self, *args):
        # If daemon is set force console logger to quiet
        if getattr(self.options, 'daemon', False) is True:
            return

        # Since we're not going to be a daemon, setup the console logger
        cli_log_fmt = 'cli_{0}_log_fmt'.format(
            self.get_prog_name().replace('-', '_')
        )
        if cli_log_fmt in self.config and not self.config.get(cli_log_fmt):
            # Remove it from config so it inherits from log_fmt_console
            self.config.pop(cli_log_fmt)

        logfmt = self.config.get(
            cli_log_fmt, self.config.get(
                'log_fmt_console',
                self.config.get(
                    'log_fmt',
                    config._DFLT_LOG_FMT_CONSOLE
                )
            )
        )

        cli_log_datefmt = 'cli_{0}_log_datefmt'.format(
            self.get_prog_name().replace('-', '_')
        )
        if cli_log_datefmt in self.config and not \
                self.config.get(cli_log_datefmt):
            # Remove it from config so it inherits from log_datefmt_console
            self.config.pop(cli_log_datefmt)

        if self.config.get('log_datefmt_console', None) is None:
            # Remove it from config so it inherits from log_datefmt
            self.config.pop('log_datefmt_console', None)

        datefmt = self.config.get(
            cli_log_datefmt,
            self.config.get(
                'log_datefmt_console',
                self.config.get(
                    'log_datefmt',
                    '%Y-%m-%d %H:%M:%S'
                )
            )
        )
        log.setup_console_logger(
            self.config['log_level'], log_format=logfmt, date_format=datefmt
        )
        for name, level in self.config['log_granular_levels'].items():
            log.set_logger_level(name, level)


class RunUserMixin(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 20

    def _mixin_setup(self):
        self.add_option(
            '-u', '--user',
            help='Specify user to run {0}'.format(self.get_prog_name())
        )


class DaemonMixIn(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 30

    def _mixin_setup(self):
        self.add_option(
            '-d', '--daemon',
            default=False,
            action='store_true',
            help='Run the {0} as a daemon'.format(self.get_prog_name())
        )

    def daemonize_if_required(self):
        if self.options.daemon:
            # Late import so logging works correctly
            import salt.utils
            salt.utils.daemonize()


class PidfileMixin(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 40

    def _mixin_setup(self):
        self.add_option(
            '--pid-file', dest='pidfile',
            default='/var/run/{0}.pid'.format(self.get_prog_name()),
            help=('Specify the location of the pidfile. Default: %default')
        )

    def set_pidfile(self):
        from salt.utils.process import set_pidfile
        set_pidfile(self.config['pidfile'], self.config['user'])


class TargetOptionsMixIn(object):

    __metaclass__ = MixInMeta
    _mixin_prio_ = 20

    selected_target_option = None

    def _mixin_setup(self):
        group = self.target_options_group = optparse.OptionGroup(
            self, 'Target Options', 'Target Selection Options'
        )
        self.add_option_group(group)
        group.add_option(
            '-E', '--pcre',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'servers, use pcre regular expressions')
        )
        group.add_option(
            '-L', '--list',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'servers, take a comma delimited list of servers.')
        )
        group.add_option(
            '-G', '--grain',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a grain value to identify targets, the syntax '
                  'for the target is the grain key followed by a glob'
                  'expression:\n"os:Arch*"')
        )
        group.add_option(
            '--grain-pcre',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a grain value to identify targets, the syntax '
                  'for the target is the grain key followed by a pcre '
                  'regular expression:\n"os:Arch.*"')
        )
        group.add_option(
            '-N', '--nodegroup',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use one of the predefined nodegroups to identify a '
                  'list of targets.')
        )
        group.add_option(
            '-R', '--range',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a range expression to identify targets. '
                  'Range expressions look like %cluster')
        )

        self._create_process_functions()

    def _create_process_functions(self):
        for option in self.target_options_group.option_list:
            def process(opt):
                if getattr(self.options, opt.dest):
                    self.selected_target_option = opt.dest

            funcname = 'process_{0}'.format(option.dest)
            if not hasattr(self, funcname):
                setattr(self, funcname, partial(process, option))

    def _mixin_after_parsed(self):
        group_options_selected = filter(
            lambda option: getattr(self.options, option.dest) is True,
            self.target_options_group.option_list
        )
        if len(group_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format('/'.join(
                    [option.get_opt_string()
                     for option in group_options_selected]))
            )
        self.config['selected_target_option'] = self.selected_target_option


class ExtendedTargetOptionsMixIn(TargetOptionsMixIn):
    def _mixin_setup(self):
        TargetOptionsMixIn._mixin_setup(self)
        group = self.target_options_group
        group.add_option(
            '-C', '--compound',
            default=False,
            action='store_true',
            help=('The compound target option allows for multiple target '
                  'types to be evaluated, allowing for greater granularity in '
                  'target matching. The compound target is space delimited, '
                  'targets other than globs are preceded with an identifier '
                  'matching the specific targets argument type: salt '
                  '\'G@os:RedHat and webser* or E@database.*\'')
        )
        group.add_option(
            '-X', '--exsel',
            default=False,
            action='store_true',
            help=('Instead of using shell globs use the return code of '
                  'a function.')
        )
        group.add_option(
            '-I', '--pillar',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a pillar value to identify targets, the syntax '
                  'for the target is the pillar key followed by a glob'
                  'expression:\n"role:production*"')
        )
        group.add_option(
            '-S', '--ipcidr',
            default=False,
            action='store_true',
            help=('Match based on Subnet (CIDR notation) or IPv4 address.')
        )

        self._create_process_functions()


class TimeoutMixIn(object):
    __metaclass__ = MixInMeta
    _mixin_prio_ = 10

    def _mixin_setup(self):
        if not hasattr(self, 'default_timeout'):
            raise RuntimeError(
                'You need to define the \'default_timeout\' attribute '
                'on {0}'.format(self.__class__.__name__)
            )
        self.add_option(
            '-t', '--timeout',
            type=int,
            default=self.default_timeout,
            help=('Change the timeout, if applicable, for the running '
                  'command; default=%default')
        )


class OutputOptionsMixIn(object):

    __metaclass__ = MixInMeta
    _mixin_prio_ = 40
    _include_text_out_ = False

    selected_output_option = None

    def _mixin_setup(self):
        group = self.output_options_group = optparse.OptionGroup(
            self, 'Output Options', 'Configure your preferred output format'
        )
        self.add_option_group(group)

        outputters = loader.outputters(
            config.minion_config(None)
        )

        group.add_option(
            '--out', '--output',
            dest='output',
            help=(
                'Print the output from the \'{0}\' command using the '
                'specified outputter. The builtins are {1}.'.format(
                    self.get_prog_name(),
                    ', '.join([repr(k) for k in outputters])
                )
            )
        )
        group.add_option(
            '--out-indent', '--output-indent',
            dest='output_indent',
            default=None,
            type=int,
            help=('Print the output indented by the provided value in spaces. '
                  'Negative values disables indentation. Only applicable in '
                  'outputters that support indentation.')
        )
        group.add_option(
            '--no-color', '--no-colour',
            default=False,
            action='store_true',
            help='Disable all colored output'
        )

        for option in self.output_options_group.option_list:
            def process(opt):
                default = self.defaults.get(opt.dest)
                if getattr(self.options, opt.dest, default) is False:
                    return
                self.selected_output_option = opt.dest

            funcname = 'process_{0}'.format(option.dest)
            if not hasattr(self, funcname):
                setattr(self, funcname, partial(process, option))

    def process_output(self):
        self.selected_output_option = self.options.output

    def _mixin_after_parsed(self):
        group_options_selected = filter(
            lambda option: (
                getattr(self.options, option.dest) and
                (option.dest.endswith('_out') or option.dest == 'output')
            ),
            self.output_options_group.option_list
        )
        if len(group_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format('/'.join([
                    option.get_opt_string() for
                    option in group_options_selected
                ]))
            )
        self.config['selected_output_option'] = self.selected_output_option


class OutputOptionsWithTextMixIn(OutputOptionsMixIn):
    # This should also be removed
    _include_text_out_ = True

    def __new__(cls, *args, **kwargs):
        instance = super(OutputOptionsWithTextMixIn, cls).__new__(cls, *args, **kwargs)
        # Let the next warning show up at least once since DeprecationWarning's
        # are, by default, ignored by python default filters
        warnings.filterwarnings(
            'once', '', DeprecationWarning, 'salt.utils.parsers'
        )
        warnings.warn(
            '\'OutputOptionsWithTextMixIn\' has been deprecated. Please '
            'start using \'OutputOptionsMixIn\', your code should not need '
            'any more change.',
            DeprecationWarning,
        )
        return instance


class MasterOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                         LogLevelMixIn, RunUserMixin, DaemonMixIn,
                         PidfileMixin):

    __metaclass__ = OptionParserMeta

    description = 'The Salt master, used to control the Salt minions.'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/master'

    def setup_config(self):
        return config.master_config(self.get_config_file_path())


class MinionOptionParser(MasterOptionParser):

    __metaclass__ = OptionParserMeta

    description = (
        'The Salt minion, receives commands from a remote Salt master.'
    )

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'minion'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/minion'

    def setup_config(self):
        return config.minion_config(self.get_config_file_path())


class SyndicOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                         LogLevelMixIn, RunUserMixin, DaemonMixIn,
                         PidfileMixin):

    __metaclass__ = OptionParserMeta

    description = (
        'A seamless master of masters. Scale Salt to thousands of hosts or '
        'across many different networks.'
    )

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/master'

    def setup_config(self):
        opts = config.master_config(self.get_config_file_path())
        user = opts.get('user', 'root')
        opts['_minion_conf_file'] = opts['conf_file']
        opts.update(config.minion_config(self.get_config_file_path('minion')))
        # Override the user from the master config file
        opts['user'] = user
        # Override the name of the PID file.
        opts['pidfile'] = '/var/run/salt-syndic.pid'

        if not opts.get('syndic_master', None):
            self.error(
                'The syndic_master needs to be configured in the salt master '
                'config, EXITING!'
            )

        # Some of the opts need to be changed to match the needed opts
        # in the minion class.
        opts['master'] = opts.get('syndic_master', opts['master'])
        try:
            opts['master_ip'] = utils.dns_check(
                opts['master'],
                ipv6=opts['ipv6']
            )
        except exceptions.SaltSystemExit as exc:
            self.exit(
                status=exc.code,
                msg='{0}: {1}\n'.format(self.get_prog_name(), exc.message)
            )

        opts['master_uri'] = 'tcp://{0}:{1}'.format(
            opts['master_ip'], str(opts['master_port'])
        )
        opts['_master_conf_file'] = opts['conf_file']
        opts.pop('conf_file')
        return opts


class SaltCMDOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                          TimeoutMixIn, ExtendedTargetOptionsMixIn,
                          OutputOptionsMixIn):

    __metaclass__ = OptionParserMeta

    default_timeout = 5

    usage = '%prog [options] \'<target>\' <function> [arguments]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/master'

    def _mixin_setup(self):
        self.add_option(
            '-s', '--static',
            default=False,
            action='store_true',
            help=('Return the data from minions as a group after they '
                  'all return.')
        )
        self.add_option(
            '--async',
            default=False,
            dest='async',
            action='store_true',
            help=('Run the salt command but don\'t wait for a reply')
        )
        self.add_option(
            '--subset',
            default=0,
            dest='subset',
            type=int,
            help=('Execute the routine on a random subset of the targetted '
                  'minions. The minions will be verified that they have the '
                  'named function before executing')
        )
        self.add_option(
            '-v', '--verbose',
            default=False,
            action='store_true',
            help=('Turn on command verbosity, display jid and active job '
                  'queries')
        )
        self.add_option(
            '-b', '--batch',
            '--batch-size',
            default='',
            dest='batch',
            help=('Execute the salt job in batch mode, pass either the number '
                  'of minions to batch at a time, or the percentage of '
                  'minions to have running')
        )
        self.add_option(
            '-a', '--auth', '--eauth', '--extended-auth',
            default='',
            dest='eauth',
            help=('Specify an extended authentication system to use.')
        )
        self.add_option(
            '-T', '--make-token',
            default=False,
            dest='mktoken',
            action='store_true',
            help=('Generate and save an authentication token for re-use. The'
                  'token is generated and made available for the period '
                  'defined in the Salt Master.')
        )
        self.add_option(
            '--return',
            default='',
            metavar='RETURNER',
            help=('Set an alternative return method. By default salt will '
                  'send the return data from the command back to the master, '
                  'but the return data can be redirected into any number of '
                  'systems, databases or applications.')
        )
        self.add_option(
            '-d', '--doc', '--documentation',
            dest='doc',
            default=False,
            action='store_true',
            help=('Return the documentation for the specified module or for '
                  'all modules if none are specified.')
        )
        self.add_option(
            '--args-separator',
            dest='args_separator',
            default=',',
            help=('Set the special argument used as a delimiter between '
                  'command arguments of compound commands. This is useful '
                  'when one wants to pass commas as arguments to '
                  'some of the commands in a compound command.')
        )

    def _mixin_after_parsed(self):
        # Catch invalid invocations of salt such as: salt run
        if len(self.args) <= 1 and not self.options.doc:
            self.print_help()
            self.exit(1)

        if self.options.doc:
            # Include the target
            if not self.args:
                self.args.insert(0, '*')
            if len(self.args) < 2:
                # Include the function
                self.args.insert(1, 'sys.doc')
            if self.args[1] != 'sys.doc':
                self.args.insert(1, 'sys.doc')
                self.args[2] = self.args[2]

        if self.options.list:
            self.config['tgt'] = self.args[0].split(',')
        else:
            self.config['tgt'] = self.args[0]

        # Detect compound command and set up the data for it
        if ',' in self.args[1]:
            self.config['fun'] = self.args[1].split(',')
            self.config['arg'] = [[]]
            cmd_index = 0
            if (self.args[2:].count(self.options.args_separator) ==
                    len(self.config['fun']) - 1):
                # new style parsing: standalone argument separator
                for arg in self.args[2:]:
                    if arg == self.options.args_separator:
                        cmd_index += 1
                        self.config['arg'].append([])
                    else:
                        self.config['arg'][cmd_index].append(arg)
            else:
                # old style parsing: argument separator can be inside args
                for arg in self.args[2:]:
                    if self.options.args_separator in arg:
                        sub_args = arg.split(self.options.args_separator)
                        for sub_arg_index, sub_arg in enumerate(sub_args):
                            if sub_arg:
                                self.config['arg'][cmd_index].append(sub_arg)
                            if sub_arg_index != len(sub_args) - 1:
                                cmd_index += 1
                                self.config['arg'].append([])
                    else:
                        self.config['arg'][cmd_index].append(arg)
                if len(self.config['fun']) != len(self.config['arg']):
                    self.exit(42, 'Cannot execute compound command without '
                                  'defining all arguments.')
        else:
            self.config['fun'] = self.args[1]
            self.config['arg'] = self.args[2:]

    def setup_config(self):
        return config.client_config(self.get_config_file_path())


class SaltCPOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                         TimeoutMixIn, TargetOptionsMixIn):
    __metaclass__ = OptionParserMeta

    description = (
        'salt-cp is NOT intended to broadcast large files, it is intended to '
        'handle text files.\nsalt-cp can be used to distribute configuration '
        'files.'
    )

    default_timeout = 5

    usage = '%prog [options] \'<target>\' SOURCE DEST'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/master'

    def _mixin_after_parsed(self):
        # salt-cp needs arguments
        if len(self.args) <= 1:
            self.print_help()
            self.exit(1)

        if self.options.list:
            self.config['tgt'] = self.args[0].split(',')
        else:
            self.config['tgt'] = self.args[0]
        self.config['src'] = self.args[1:-1]
        self.config['dest'] = self.args[-1]

    def setup_config(self):
        return config.master_config(self.get_config_file_path())


class SaltKeyOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                          LogLevelMixIn, OutputOptionsMixIn):

    __metaclass__ = OptionParserMeta

    description = 'Salt key is used to manage Salt authentication keys'

    usage = '%prog [options]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _skip_console_logging_config_ = True
    _logfile_config_setting_name_ = 'key_logfile'
    _default_logging_logfile_ = '/var/log/salt/key'

    def _mixin_setup(self):
        # XXX: Remove '--key-logfile' support in 0.18.0
        self.logging_options_group.add_option(
            '--key-logfile',
            default=None,
            help='Send all output to a file. Default is {0!r}'.format(
                self._default_logging_logfile_
            )
        )

        actions_group = optparse.OptionGroup(self, 'Actions')
        actions_group.add_option(
            '-l', '--list',
            default='',
            metavar='ARG',
            help=('List the public keys. The args '
                  '"pre", "un", and "unaccepted" will list '
                  'unaccepted/unsigned keys. '
                  '"acc" or "accepted" will list accepted/signed keys. '
                  '"rej" or "rejected" will list rejected keys. '
                  'Finally, "all" will list all keys.')
        )

        actions_group.add_option(
            '-L', '--list-all',
            default=False,
            action='store_true',
            help='List all public keys. Deprecated: use "--list all"'
        )

        actions_group.add_option(
            '-a', '--accept',
            default='',
            help='Accept the following key'
        )

        actions_group.add_option(
            '-A', '--accept-all',
            default=False,
            action='store_true',
            help='Accept all pending keys'
        )

        actions_group.add_option(
            '-r', '--reject',
            default='',
            help='Reject the specified public key'
        )

        actions_group.add_option(
            '-R', '--reject-all',
            default=False,
            action='store_true',
            help='Reject all pending keys'
        )

        actions_group.add_option(
            '-p', '--print',
            default='',
            help='Print the specified public key'
        )

        actions_group.add_option(
            '-P', '--print-all',
            default=False,
            action='store_true',
            help='Print all public keys'
        )

        actions_group.add_option(
            '-d', '--delete',
            default='',
            help='Delete the named key'
        )

        actions_group.add_option(
            '-D', '--delete-all',
            default=False,
            action='store_true',
            help='Delete all keys'
        )

        actions_group.add_option(
            '-f', '--finger',
            default='',
            help='Print the named key\'s fingerprint'
        )

        actions_group.add_option(
            '-F', '--finger-all',
            default=False,
            action='store_true',
            help='Print all key\'s fingerprints'
        )
        self.add_option_group(actions_group)

        self.add_option(
            '-q', '--quiet',
            default=False,
            action='store_true',
            help='Suppress output'
        )

        self.add_option(
            '-y', '--yes',
            default=False,
            action='store_true',
            help='Answer Yes to all questions presented, defaults to False'
        )

        key_options_group = optparse.OptionGroup(
            self, 'Key Generation Options'
        )
        self.add_option_group(key_options_group)
        key_options_group.add_option(
            '--gen-keys',
            default='',
            help='Set a name to generate a keypair for use with salt'
        )

        key_options_group.add_option(
            '--gen-keys-dir',
            default='.',
            help=('Set the directory to save the generated keypair, only '
                  'works with "gen_keys_dir" option; default=.')
        )

        key_options_group.add_option(
            '--keysize',
            default=2048,
            type=int,
            help=('Set the keysize for the generated key, only works with '
                  'the "--gen-keys" option, the key size must be 2048 or '
                  'higher, otherwise it will be rounded up to 2048; '
                  '; default=%default')
        )

    def process_config_dir(self):
        if self.options.gen_keys:
            # We're generating keys, override the default behaviour of this
            # function if we don't have any access to the configuration
            # directory.
            if not os.access(self.options.config_dir, os.R_OK):
                if not os.path.isdir(self.options.gen_keys_dir):
                    # This would be done at a latter stage, but we need it now
                    # so no errors are thrown
                    os.makedirs(self.options.gen_keys_dir)
                self.options.config_dir = self.options.gen_keys_dir
        super(SaltKeyOptionParser, self).process_config_dir()
    # Don't change it's mixin priority!
    process_config_dir._mixin_prio_ = ConfigDirMixIn._mixin_prio_

    def setup_config(self):
        keys_config = config.master_config(self.get_config_file_path())
        if self.options.gen_keys:
            # Since we're generating the keys, some defaults can be assumed
            # or tweaked
            keys_config['key_logfile'] = os.devnull
            keys_config['pki_dir'] = self.options.gen_keys_dir

        return keys_config

    def process_keysize(self):
        if self.options.keysize < 2048:
            self.error('The minimum value for keysize is 2048')
        elif self.options.keysize > 32768:
            self.error('The maximum value for keysize is 32768')

    def process_gen_keys_dir(self):
        # Schedule __create_keys_dir() to run if there's a value for
        # --create-keys-dir
        self._mixin_after_parsed_funcs.append(self.__create_keys_dir)

    def process_key_logfile(self):
        if self.options.key_logfile:
            # XXX: Remove '--key-logfile' support in 0.18.0
            # In < 0.18.0 error out
            self.error(
                'The \'--key-logfile\' option has been deprecated in favour '
                'of \'--log-file\''
            )

    def _mixin_after_parsed(self):
        # It was decided to always set this to info, since it really all is
        # info or error.
        self.config['loglevel'] = 'info'

    def __create_keys_dir(self, *args):
        if not os.path.isdir(self.config['gen_keys_dir']):
            os.makedirs(self.config['gen_keys_dir'])


class SaltCallOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                           LogLevelMixIn, OutputOptionsMixIn):
    __metaclass__ = OptionParserMeta

    description = ('Salt call is used to execute module functions locally '
                   'on a minion')

    usage = '%prog [options] <function> [arguments]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'minion'

    # LogLevelMixIn attributes
    _default_logging_level_ = 'info'
    _default_logging_logfile_ = '/var/log/salt/minion'

    def _mixin_setup(self):
        self.add_option(
            '-g', '--grains',
            dest='grains_run',
            default=False,
            action='store_true',
            help='Return the information generated by the salt grains'
        )
        self.add_option(
            '-m', '--module-dirs',
            default=[],
            action='append',
            help=('Specify an additional directory to pull modules from. '
                  'Multiple directories can be provided by passing '
                  '`-m/--module-dirs` multiple times.')
        )
        self.add_option(
            '-d', '--doc', '--documentation',
            dest='doc',
            default=False,
            action='store_true',
            help=('Return the documentation for the specified module or for '
                  'all modules if none are specified.')
        )
        self.add_option(
            '--master',
            default='',
            dest='master',
            help=('Specify the master to use. The minion must be '
                  'authenticated with the master. If this option is omitted, '
                  'the master options from the minion config will be used. '
                  'If multi masters are set up the first listed master that '
                  'responds will be used.')
        )
        self.add_option(
            '--return',
            default='',
            metavar='RETURNER',
            help=('Set salt-call to pass the return data to one or many '
                  'returner interfaces.')
        )
        self.add_option(
            '--local',
            default=False,
            action='store_true',
            help='Run salt-call locally, as if there was no master running.'
        )

    def _mixin_after_parsed(self):
        if not self.args and not self.options.grains_run \
                and not self.options.doc:
            self.print_help()
            self.exit(1)

        elif len(self.args) >= 1:
            if self.options.grains_run:
                self.error('-g/--grains does not accept any arguments')

            self.config['fun'] = self.args[0]
            self.config['arg'] = self.args[1:]

    def setup_config(self):
        return config.minion_config(self.get_config_file_path())

    def process_module_dirs(self):
        for module_dir in self.options.module_dirs:
            # Provide some backwards compatibility with previous comma
            # delimited format
            if ',' in module_dir:
                self.config.setdefault('module_dirs', []).extend(
                    os.path.abspath(x) for x in module_dir.split(','))
                continue
            self.config.setdefault('module_dirs',
                                   []).append(os.path.abspath(module_dir))


class SaltRunOptionParser(OptionParser, ConfigDirMixIn, MergeConfigMixIn,
                          TimeoutMixIn):
    __metaclass__ = OptionParserMeta

    default_timeout = 1

    usage = '%prog [options]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = '/var/log/salt/master'

    def _mixin_setup(self):
        self.add_option(
            '-d', '--doc', '--documentation',
            dest='doc',
            default=False,
            action='store_true',
            help=('Display documentation for runners, pass a module or a '
                  'runner to see documentation on only that module/runner.')
        )

    def _mixin_after_parsed(self):
        if len(self.args) > 0:
            self.config['fun'] = self.args[0]
        else:
            self.config['fun'] = ''
        if len(self.args) > 1:
            self.config['arg'] = self.args[1:]
        else:
            self.config['arg'] = []

    def setup_config(self):
        return config.master_config(self.get_config_file_path())
