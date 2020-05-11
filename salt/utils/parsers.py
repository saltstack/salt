# -*- coding: utf-8 -*-
'''
    :codeauthor: Pedro Algarvio (pedro@algarvio.me)


    salt.utils.parsers
    ~~~~~~~~~~~~~~~~~~

    This is where all the black magic happens on all of salt's CLI tools.
'''
# pylint: disable=missing-docstring,protected-access,too-many-ancestors,too-few-public-methods
# pylint: disable=attribute-defined-outside-init,no-self-use

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import sys
import signal
import getpass
import logging
import optparse
import traceback
import tempfile
from functools import partial


# Import salt libs
import salt.config as config
import salt.defaults.exitcodes
import salt.log.setup as log
import salt.syspaths as syspaths
import salt.version as version
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.jid
import salt.utils.network
import salt.utils.platform
import salt.utils.process
import salt.utils.stringutils
import salt.utils.user
import salt.utils.win_functions
import salt.utils.xdg
import salt.utils.yaml
from salt.defaults import DEFAULT_TARGET_DELIM
from salt.utils.validate.path import is_writeable
from salt.utils.verify import verify_files
import salt.exceptions
from salt.ext import six
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin

logger = logging.getLogger(__name__)


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
                "Don't subclass {0} in {1} if you're not going "
                "to use it as a salt parser mix-in.".format(mcs.__name__, name)
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
        if not hasattr(instance, '_mixin_before_exit_funcs'):
            instance._mixin_before_exit_funcs = []

        for base in _sorted(bases + (instance,)):
            func = getattr(base, '_mixin_setup', None)
            if func is not None and func not in instance._mixin_setup_funcs:
                instance._mixin_setup_funcs.append(func)

            func = getattr(base, '_mixin_after_parsed', None)
            if func is not None and func not in \
                    instance._mixin_after_parsed_funcs:
                instance._mixin_after_parsed_funcs.append(func)

            func = getattr(base, '_mixin_before_exit', None)
            if func is not None and func not in \
                    instance._mixin_before_exit_funcs:
                instance._mixin_before_exit_funcs.append(func)

            # Mark process_<opt> functions with the base priority for sorting
            for func in dir(base):
                if not func.startswith('process_'):
                    continue

                func = getattr(base, func)
                if getattr(func, '_mixin_prio_', None) is not None:
                    # Function already has the attribute set, don't override it
                    continue

                if six.PY2:
                    func.__func__._mixin_prio_ = getattr(
                        base, '_mixin_prio_', 1000
                    )
                else:
                    func._mixin_prio_ = getattr(
                        base, '_mixin_prio_', 1000
                    )

        return instance


class CustomOption(optparse.Option, object):
    def take_action(self, action, dest, *args, **kwargs):
        # see https://github.com/python/cpython/blob/master/Lib/optparse.py#L786
        self.explicit = True
        return optparse.Option.take_action(self, action, dest, *args, **kwargs)


class OptionParser(optparse.OptionParser, object):
    VERSION = version.__saltstack_version__.formatted_version

    usage = '%prog [options]'

    epilog = ('You can find additional help about %prog issuing "man %prog" '
              'or on http://docs.saltstack.com')
    description = None

    # Private attributes
    _mixin_prio_ = 100

    # Setup multiprocessing logging queue listener
    _setup_mp_logging_listener_ = False

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('version', '%prog {0}'.format(self.VERSION))
        kwargs.setdefault('usage', self.usage)
        if self.description:
            kwargs.setdefault('description', self.description)

        if self.epilog:
            kwargs.setdefault('epilog', self.epilog)

        kwargs.setdefault('option_class', CustomOption)
        optparse.OptionParser.__init__(self, *args, **kwargs)

        if self.epilog and '%prog' in self.epilog:
            self.epilog = self.epilog.replace('%prog', self.get_prog_name())

    def add_option_group(self, *args, **kwargs):
        option_group = optparse.OptionParser.add_option_group(self, *args, **kwargs)
        option_group.option_class = CustomOption
        return option_group

    def parse_args(self, args=None, values=None):
        options, args = optparse.OptionParser.parse_args(self, args, values)
        if 'args_stdin' in options.__dict__ and options.args_stdin is True:
            # Read additional options and/or arguments from stdin and combine
            # them with the options and arguments from the command line.
            new_inargs = sys.stdin.readlines()
            new_inargs = [arg.rstrip('\r\n') for arg in new_inargs]
            new_options, new_args = optparse.OptionParser.parse_args(
                self,
                new_inargs)
            options.__dict__.update(new_options.__dict__)
            args.extend(new_args)

        if six.PY2:
            args = salt.utils.data.decode(args)

        if options.versions_report:
            self.print_versions_report()

        self.options, self.args = options, args

        # Let's get some proper sys.stderr logging as soon as possible!!!
        # This logging handler will be removed once the proper console or
        # logfile logging is setup.
        temp_log_level = getattr(self.options, 'log_level', None)
        log.setup_temp_logger(
            'error' if temp_log_level is None else temp_log_level
        )

        # Gather and run the process_<option> functions in the proper order
        process_option_funcs = []
        for option_key in options.__dict__:
            process_option_func = getattr(
                self, 'process_{0}'.format(option_key), None
            )
            if process_option_func is not None:
                process_option_funcs.append(process_option_func)

        for process_option_func in _sorted(process_option_funcs):
            try:
                process_option_func()
            except Exception as err:  # pylint: disable=broad-except
                logger.exception(err)
                self.error(
                    'Error while processing {0}: {1}'.format(
                        process_option_func, traceback.format_exc(err)
                    )
                )

        # Run the functions on self._mixin_after_parsed_funcs
        for mixin_after_parsed_func in self._mixin_after_parsed_funcs:  # pylint: disable=no-member
            try:
                mixin_after_parsed_func(self)
            except Exception as err:  # pylint: disable=broad-except
                logger.exception(err)
                self.error(
                    'Error while processing {0}: {1}'.format(
                        mixin_after_parsed_func, traceback.format_exc(err)
                    )
                )

        if self.config.get('conf_file', None) is not None:  # pylint: disable=no-member
            logger.debug(
                'Configuration file path: %s',
                self.config['conf_file']  # pylint: disable=no-member
            )
        # Retain the standard behavior of optparse to return options and args
        return options, args

    def _populate_option_list(self, option_list, add_help=True):
        optparse.OptionParser._populate_option_list(
            self, option_list, add_help=add_help
        )
        for mixin_setup_func in self._mixin_setup_funcs:  # pylint: disable=no-member
            mixin_setup_func(self)

    def _add_version_option(self):
        optparse.OptionParser._add_version_option(self)
        self.add_option(
            '--versions-report',
            '-V',
            action='store_true',
            help='Show program\'s dependencies version number and exit.'
        )

    def print_versions_report(self, file=sys.stdout):  # pylint: disable=redefined-builtin
        print('\n'.join(version.versions_report()), file=file)
        self.exit(salt.defaults.exitcodes.EX_OK)

    def exit(self, status=0, msg=None):
        # Run the functions on self._mixin_after_parsed_funcs
        for mixin_before_exit_func in self._mixin_before_exit_funcs:  # pylint: disable=no-member
            try:
                mixin_before_exit_func(self)
            except Exception as err:  # pylint: disable=broad-except
                logger.exception(err)
                logger.error('Error while processing %s: %s',
                             six.text_type(mixin_before_exit_func),
                             traceback.format_exc(err))
        if self._setup_mp_logging_listener_ is True:
            # Stop logging through the queue
            log.shutdown_multiprocessing_logging()
            # Stop the logging queue listener process
            log.shutdown_multiprocessing_logging_listener(daemonizing=True)
        if isinstance(msg, six.string_types) and msg and msg[-1] != '\n':
            msg = '{0}\n'.format(msg)
        optparse.OptionParser.exit(self, status, msg)

    def error(self, msg):
        '''
        error(msg : string)

        Print a usage message incorporating 'msg' to stderr and exit.
        This keeps option parsing exit status uniform for all parsing errors.
        '''
        self.print_usage(sys.stderr)
        self.exit(salt.defaults.exitcodes.EX_USAGE, '{0}: error: {1}\n'.format(self.get_prog_name(), msg))


class MergeConfigMixIn(six.with_metaclass(MixInMeta, object)):
    '''
    This mix-in will simply merge the CLI-passed options, by overriding the
    configuration file loaded settings.

    This mix-in should run last.
    '''
    _mixin_prio_ = six.MAXSIZE

    def _mixin_setup(self):
        if not hasattr(self, 'setup_config') and not hasattr(self, 'config'):
            # No configuration was loaded on this parser.
            # There's nothing to do here.
            return

        # Add an additional function that will merge the shell options with
        # the config options and if needed override them
        self._mixin_after_parsed_funcs.append(self.__merge_config_with_cli)

    def __merge_config_with_cli(self, *args):  # pylint: disable=unused-argument
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
            elif value is not None and getattr(option, 'explicit', False):
                # Only set the value in the config file IF it was explicitly
                # specified by the user, this makes it possible to tweak settings
                # on the configuration files bypassing the shell option flags'
                # defaults
                self.config[option.dest] = value
            elif option.dest in self.config:
                # Let's update the option value with the one from the
                # configuration file. This allows the parsers to make use of
                # the updated value by using self.options.<option>
                setattr(self.options, option.dest, self.config[option.dest])

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
                elif value is not None and getattr(option, 'explicit', False):
                    # Only set the value in the config file IF it was explicitly
                    # specified by the user, this makes it possible to tweak
                    # settings on the configuration files bypassing the shell
                    # option flags' defaults
                    self.config[option.dest] = value
                elif option.dest in self.config:
                    # Let's update the option value with the one from the
                    # configuration file. This allows the parsers to make use
                    # of the updated value by using self.options.<option>
                    setattr(self.options,
                            option.dest,
                            self.config[option.dest])


class SaltfileMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = -20

    def _mixin_setup(self):
        self.add_option(
            '--saltfile', default=None,
            help='Specify the path to a Saltfile. If not passed, one will be '
                 'searched for in the current working directory.'
        )

    def process_saltfile(self):
        if self.options.saltfile is None:
            # No one passed a Saltfile as an option, environment variable!?
            self.options.saltfile = os.environ.get('SALT_SALTFILE', None)

        if self.options.saltfile is None:
            # If we're here, no one passed a Saltfile either to the CLI tool or
            # as an environment variable.
            # Is there a Saltfile in the current directory?
            try:  # cwd may not exist if it was removed but salt was run from it
                saltfile = os.path.join(os.getcwd(), 'Saltfile')
            except OSError:
                saltfile = ''
            if os.path.isfile(saltfile):
                self.options.saltfile = saltfile
            else:
                saltfile = os.path.join(os.path.expanduser("~"), '.salt', 'Saltfile')
                if os.path.isfile(saltfile):
                    self.options.saltfile = saltfile
        else:
            saltfile = self.options.saltfile

        if not self.options.saltfile:
            # There's still no valid Saltfile? No need to continue...
            return

        if not os.path.isfile(self.options.saltfile):
            self.error("'{0}' file does not exist.\n".format(self.options.saltfile))

        # Make sure we have an absolute path
        self.options.saltfile = os.path.abspath(self.options.saltfile)

        # Make sure we let the user know that we will be loading a Saltfile
        logger.info("Loading Saltfile from '%s'", six.text_type(self.options.saltfile))

        try:
            saltfile_config = config._read_conf_file(saltfile)
        except salt.exceptions.SaltConfigurationError as error:
            self.error(error.message)
            self.exit(salt.defaults.exitcodes.EX_GENERIC,
                      '{0}: error: {1}\n'.format(self.get_prog_name(), error.message))

        if not saltfile_config:
            # No configuration was loaded from the Saltfile
            return

        if self.get_prog_name() not in saltfile_config:
            # There's no configuration specific to the CLI tool. Stop!
            return

        # We just want our own configuration
        cli_config = saltfile_config[self.get_prog_name()]

        # If there are any options, who's names match any key from the loaded
        # Saltfile, we need to update its default value
        for option in self.option_list:
            if option.dest is None:
                # --version does not have dest attribute set for example.
                continue

            if option.dest not in cli_config:
                # If we don't have anything in Saltfile for this option, let's
                # continue processing right now
                continue

            # Get the passed value from shell. If empty get the default one
            default = self.defaults.get(option.dest)
            value = getattr(self.options, option.dest, default)
            if value != default:
                # The user passed an argument, we won't override it with the
                # one from Saltfile, if any
                continue

            # We reached this far! Set the Saltfile value on the option
            setattr(self.options, option.dest, cli_config[option.dest])
            option.explicit = True

        # Let's also search for options referred in any option groups
        for group in self.option_groups:
            for option in group.option_list:
                if option.dest is None:
                    continue

                if option.dest not in cli_config:
                    # If we don't have anything in Saltfile for this option,
                    # let's continue processing right now
                    continue

                # Get the passed value from shell. If empty get the default one
                default = self.defaults.get(option.dest)
                value = getattr(self.options, option.dest, default)
                if value != default:
                    # The user passed an argument, we won't override it with
                    # the one from Saltfile, if any
                    continue

                setattr(self.options, option.dest, cli_config[option.dest])
                option.explicit = True

        # Any left over value in the saltfile can now be safely added
        for key in cli_config:
            setattr(self.options, key, cli_config[key])


class HardCrashMixin(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 40
    _config_filename_ = None

    def _mixin_setup(self):
        hard_crash = os.environ.get('SALT_HARD_CRASH', False)
        self.add_option(
            '--hard-crash', action='store_true', default=hard_crash,
            help='Raise any original exception rather than exiting gracefully. Default: %default.'
        )


class NoParseMixin(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 50

    def _mixin_setup(self):
        no_parse = os.environ.get('SALT_NO_PARSE', '')
        self.add_option(
            '--no-parse', default=no_parse,
            help='Comma-separated list of named CLI arguments (i.e. argname=value) '
                 'which should not be parsed as Python data types',
            metavar='argname1,argname2,...',
        )

    def process_no_parse(self):
        if self.options.no_parse:
            try:
                self.options.no_parse = \
                    [x.strip() for x in self.options.no_parse.split(',')]
            except AttributeError:
                self.options.no_parse = []
        else:
            self.options.no_parse = []


class ConfigDirMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = -10
    _config_filename_ = None
    _default_config_dir_ = syspaths.CONFIG_DIR
    _default_config_dir_env_var_ = 'SALT_CONFIG_DIR'

    def _mixin_setup(self):
        config_dir = os.environ.get(self._default_config_dir_env_var_, None)
        if not config_dir:
            config_dir = self._default_config_dir_
            logger.debug('SYSPATHS setup as: %s', six.text_type(syspaths.CONFIG_DIR))
        self.add_option(
            '-c', '--config-dir', default=config_dir,
            help="Pass in an alternative configuration directory. Default: '%default'."
        )

    def process_config_dir(self):
        self.options.config_dir = os.path.expanduser(self.options.config_dir)
        config_filename = self.get_config_file_path()
        if not os.path.isdir(self.options.config_dir):
            # No logging is configured yet
            sys.stderr.write(
                "WARNING: CONFIG '{0}' directory does not exist.\n".format(
                    self.options.config_dir
                )
            )
        elif not os.path.isfile(config_filename):
            default_config_filename = os.path.join(
                self._default_config_dir_,
                os.path.split(config_filename)[-1],
            )
            sys.stderr.write(
                "WARNING: CONFIG '{0}' file does not exist. Falling back to default '{1}'.\n".format(
                    config_filename,
                    default_config_filename,
                )
            )

        # Make sure we have an absolute path
        self.options.config_dir = os.path.abspath(self.options.config_dir)

        if hasattr(self, 'setup_config'):
            if not hasattr(self, 'config'):
                self.config = {}
            try:
                self.config.update(self.setup_config())
            except (IOError, OSError) as exc:
                self.error('Failed to load configuration: {0}'.format(exc))

    def get_config_file_path(self, configfile=None):
        if configfile is None:
            configfile = self._config_filename_
        return os.path.join(self.options.config_dir, configfile)


class LogLevelMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 10
    _default_logging_level_ = 'warning'
    _default_logging_logfile_ = None
    _logfile_config_setting_name_ = 'log_file'
    _loglevel_config_setting_name_ = 'log_level'
    _logfile_loglevel_config_setting_name_ = 'log_level_logfile'  # pylint: disable=invalid-name
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
                dest=self._loglevel_config_setting_name_,
                choices=list(log.LOG_LEVELS),
                help='Console logging log level. One of {0}. Default: \'{1}\'.'.format(
                     ', '.join(["'{}'".format(n) for n in log.SORTED_LEVEL_NAMES]),
                     self._default_logging_level_
                )
            )

        def _logfile_callback(option, opt, value, parser, *args, **kwargs):
            if not os.path.dirname(value):
                # if the path is only a file name (no parent directory), assume current directory
                value = os.path.join(os.path.curdir, value)
            setattr(parser.values, self._logfile_config_setting_name_, value)

        group.add_option(
            '--log-file',
            dest=self._logfile_config_setting_name_,
            default=None,
            action='callback',
            type='string',
            callback=_logfile_callback,
            help='Log file path. Default: \'{0}\'.'.format(
                self._default_logging_logfile_
            )
        )

        group.add_option(
            '--log-file-level',
            dest=self._logfile_loglevel_config_setting_name_,
            choices=list(log.LOG_LEVELS),
            help='Logfile logging log level. One of {0}. Default: \'{1}\'.'.format(
                 ', '.join(["'{}'".format(n) for n in log.SORTED_LEVEL_NAMES]),
                 self._default_logging_level_
            )
        )

    def process_log_level(self):
        if not getattr(self.options, self._loglevel_config_setting_name_, None):
            # Log level is not set via CLI, checking loaded configuration
            if self.config.get(self._loglevel_config_setting_name_, None):
                # Is the regular log level setting set?
                setattr(self.options,
                        self._loglevel_config_setting_name_,
                        self.config.get(self._loglevel_config_setting_name_))
            else:
                # Nothing is set on the configuration? Let's use the CLI tool
                # defined default
                setattr(self.options,
                        self._loglevel_config_setting_name_,
                        self._default_logging_level_)

        # Setup extended logging right before the last step
        self._mixin_after_parsed_funcs.append(self.__setup_extended_logging)
        # Setup the console and log file configuration before the MP logging
        # listener because the MP logging listener may need that config.
        self._mixin_after_parsed_funcs.append(self.__setup_logfile_logger_config)
        self._mixin_after_parsed_funcs.append(self.__setup_console_logger_config)
        # Setup the multiprocessing log queue listener if enabled
        self._mixin_after_parsed_funcs.append(self._setup_mp_logging_listener)
        # Setup the multiprocessing log queue client if listener is enabled
        # and using Windows
        self._mixin_after_parsed_funcs.append(self._setup_mp_logging_client)
        # Setup the console as the last _mixin_after_parsed_func to run
        self._mixin_after_parsed_funcs.append(self.__setup_console_logger)

    def process_log_file(self):
        if not getattr(self.options, self._logfile_config_setting_name_, None):
            # Log file is not set via CLI, checking loaded configuration
            if self.config.get(self._logfile_config_setting_name_, None):
                # Is the regular log file setting set?
                setattr(self.options,
                        self._logfile_config_setting_name_,
                        self.config.get(self._logfile_config_setting_name_))
            else:
                # Nothing is set on the configuration? Let's use the CLI tool
                # defined default
                setattr(self.options,
                        self._logfile_config_setting_name_,
                        self._default_logging_logfile_)
                if self._logfile_config_setting_name_ in self.config:
                    # Remove it from config so it inherits from log_file
                    self.config.pop(self._logfile_config_setting_name_)

    def process_log_level_logfile(self):
        if not getattr(self.options, self._logfile_loglevel_config_setting_name_, None):
            # Log file level is not set via CLI, checking loaded configuration
            if self.config.get(self._logfile_loglevel_config_setting_name_, None):
                # Is the regular log file level setting set?
                setattr(self.options,
                        self._logfile_loglevel_config_setting_name_,
                        self.config.get(self._logfile_loglevel_config_setting_name_))
            else:
                # Nothing is set on the configuration? Let's use the CLI tool
                # defined default
                setattr(self.options,
                        self._logfile_loglevel_config_setting_name_,
                        # From the console log level config setting
                        self.config.get(
                            self._loglevel_config_setting_name_,
                            self._default_logging_level_
                        ))
                if self._logfile_loglevel_config_setting_name_ in self.config:
                    # Remove it from config so it inherits from log_level_logfile
                    self.config.pop(self._logfile_loglevel_config_setting_name_)

    def __setup_logfile_logger_config(self, *args):  # pylint: disable=unused-argument
        if self._logfile_loglevel_config_setting_name_ in self.config and not \
                self.config.get(self._logfile_loglevel_config_setting_name_):
            # Remove it from config so it inherits from log_level
            self.config.pop(self._logfile_loglevel_config_setting_name_)

        loglevel = getattr(self.options,
                           # From the options setting
                           self._logfile_loglevel_config_setting_name_,
                           # From the default setting
                           self._default_logging_level_
                           )

        logfile = getattr(self.options,
                          # From the options setting
                          self._logfile_config_setting_name_,
                          # From the default setting
                          self._default_logging_logfile_
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

        if self.config['verify_env'] and self.config['log_level'] not in ('quiet', ):
            # Verify the logfile if it was explicitly set but do not try to
            # verify the default
            if logfile is not None and not logfile.startswith(('tcp://', 'udp://', 'file://')):
                # Logfile is not using Syslog, verify
                with salt.utils.files.set_umask(0o027):
                    verify_files([logfile], self.config['user'])

        if logfile is None:
            # Use the default setting if the logfile wasn't explicity set
            logfile = self._default_logging_logfile_

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
            'log_fmt_logfile',
            self.config.get(
                'log_fmt_console',
                self.config.get(
                    'log_fmt',
                    config._DFLT_LOG_FMT_CONSOLE
                )
            )
        )

        if self.config.get('log_datefmt_logfile', None) is None:
            # Remove it from config so it inherits from log_datefmt_console
            self.config.pop('log_datefmt_logfile', None)

        if self.config.get('log_datefmt_console', None) is None:
            # Remove it from config so it inherits from log_datefmt
            self.config.pop('log_datefmt_console', None)

        log_file_datefmt = self.config.get(
            'log_datefmt_logfile',
            self.config.get(
                'log_datefmt_console',
                self.config.get(
                    'log_datefmt',
                    '%Y-%m-%d %H:%M:%S'
                )
            )
        )

        if not is_writeable(logfile, check_parent=True):
            # Since we're not be able to write to the log file or its parent
            # directory (if the log file does not exit), are we the same user
            # as the one defined in the configuration file?
            current_user = salt.utils.user.get_user()
            if self.config['user'] != current_user:
                # Yep, not the same user!
                # Is the current user in ACL?
                acl = self.config['publisher_acl']
                if salt.utils.stringutils.check_whitelist_blacklist(
                            current_user, whitelist=six.iterkeys(acl)):
                    # Yep, the user is in ACL!
                    # Let's write the logfile to its home directory instead.
                    xdg_dir = salt.utils.xdg.xdg_config_dir()
                    user_salt_dir = (xdg_dir if os.path.isdir(xdg_dir) else
                                     os.path.expanduser('~/.salt'))

                    if not os.path.isdir(user_salt_dir):
                        os.makedirs(user_salt_dir, 0o750)
                    logfile_basename = os.path.basename(
                        self._default_logging_logfile_
                    )
                    logger.debug("The user '%s' is not allowed to write to '%s'. "
                                 "The log file will be stored in '~/.salt/'%s'.log'",
                                 six.text_type(current_user),
                                 six.text_type(logfile),
                                 six.text_type(logfile_basename))
                    logfile = os.path.join(
                        user_salt_dir, '{0}.log'.format(logfile_basename)
                    )

            # If we haven't changed the logfile path and it's not writeable,
            # salt will fail once we try to setup the logfile logging.

        # Log rotate options
        log_rotate_max_bytes = self.config.get('log_rotate_max_bytes', 0)
        log_rotate_backup_count = self.config.get('log_rotate_backup_count', 0)
        if not salt.utils.platform.is_windows():
            # Not supported on platforms other than Windows.
            # Other platforms may use an external tool such as 'logrotate'
            if log_rotate_max_bytes != 0:
                logger.warning("'log_rotate_max_bytes' is only supported on Windows")
                log_rotate_max_bytes = 0
            if log_rotate_backup_count != 0:
                logger.warning("'log_rotate_backup_count' is only supported on Windows")
                log_rotate_backup_count = 0

        # Save the settings back to the configuration
        self.config[self._logfile_config_setting_name_] = logfile
        self.config[self._logfile_loglevel_config_setting_name_] = loglevel
        self.config['log_fmt_logfile'] = log_file_fmt
        self.config['log_datefmt_logfile'] = log_file_datefmt
        self.config['log_rotate_max_bytes'] = log_rotate_max_bytes
        self.config['log_rotate_backup_count'] = log_rotate_backup_count

    def setup_logfile_logger(self):
        if salt.utils.platform.is_windows() and self._setup_mp_logging_listener_:
            # On Windows when using a logging listener, all log file logging
            # will go through the logging listener.
            return

        logfile = self.config[self._logfile_config_setting_name_]
        loglevel = self.config[self._logfile_loglevel_config_setting_name_]
        log_file_fmt = self.config['log_fmt_logfile']
        log_file_datefmt = self.config['log_datefmt_logfile']
        log_rotate_max_bytes = self.config['log_rotate_max_bytes']
        log_rotate_backup_count = self.config['log_rotate_backup_count']

        log.setup_logfile_logger(
            logfile,
            loglevel,
            log_format=log_file_fmt,
            date_format=log_file_datefmt,
            max_bytes=log_rotate_max_bytes,
            backup_count=log_rotate_backup_count
        )
        for name, level in six.iteritems(self.config.get('log_granular_levels', {})):
            log.set_logger_level(name, level)

    def __setup_extended_logging(self, *args):  # pylint: disable=unused-argument
        if salt.utils.platform.is_windows() and self._setup_mp_logging_listener_:
            # On Windows when using a logging listener, all extended logging
            # will go through the logging listener.
            return
        log.setup_extended_logging(self.config)

    def _get_mp_logging_listener_queue(self):
        return log.get_multiprocessing_logging_queue()

    def _setup_mp_logging_listener(self, *args):  # pylint: disable=unused-argument
        if self._setup_mp_logging_listener_:
            log.setup_multiprocessing_logging_listener(
                self.config,
                self._get_mp_logging_listener_queue()
            )

    def _setup_mp_logging_client(self, *args):  # pylint: disable=unused-argument
        if self._setup_mp_logging_listener_:
            # Set multiprocessing logging level even in non-Windows
            # environments. In non-Windows environments, this setting will
            # propogate from process to process via fork behavior and will be
            # used by child processes if they invoke the multiprocessing
            # logging client.
            log.set_multiprocessing_logging_level_by_opts(self.config)

            if salt.utils.platform.is_windows():
                # On Windows, all logging including console and
                # log file logging will go through the multiprocessing
                # logging listener if it exists.
                # This will allow log file rotation on Windows
                # since only one process can own the log file
                # for log file rotation to work.
                log.setup_multiprocessing_logging(
                    self._get_mp_logging_listener_queue()
                )
                # Remove the temp logger and any other configured loggers since
                # all of our logging is going through the multiprocessing
                # logging listener.
                log.shutdown_temp_logging()
                log.shutdown_console_logging()
                log.shutdown_logfile_logging()

    def __setup_console_logger_config(self, *args):  # pylint: disable=unused-argument
        # Since we're not going to be a daemon, setup the console logger
        logfmt = self.config.get(
            'log_fmt_console',
            self.config.get(
                'log_fmt',
                config._DFLT_LOG_FMT_CONSOLE
            )
        )

        if self.config.get('log_datefmt_console', None) is None:
            # Remove it from config so it inherits from log_datefmt
            self.config.pop('log_datefmt_console', None)

        datefmt = self.config.get(
            'log_datefmt_console',
            self.config.get(
                'log_datefmt',
                '%Y-%m-%d %H:%M:%S'
            )
        )

        # Save the settings back to the configuration
        self.config['log_fmt_console'] = logfmt
        self.config['log_datefmt_console'] = datefmt

    def __setup_console_logger(self, *args):  # pylint: disable=unused-argument
        # If daemon is set force console logger to quiet
        if getattr(self.options, 'daemon', False) is True:
            return

        if salt.utils.platform.is_windows() and self._setup_mp_logging_listener_:
            # On Windows when using a logging listener, all console logging
            # will go through the logging listener.
            return

        # ensure that yaml stays valid with log output
        if getattr(self.options, 'output', None) == 'yaml':
            log_format = '# {0}'.format(self.config['log_fmt_console'])
        else:
            log_format = self.config['log_fmt_console']

        log.setup_console_logger(
            self.config['log_level'],
            log_format=log_format,
            date_format=self.config['log_datefmt_console']
        )
        for name, level in six.iteritems(self.config.get('log_granular_levels', {})):
            log.set_logger_level(name, level)


class RunUserMixin(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 20

    def _mixin_setup(self):
        self.add_option(
            '-u', '--user',
            help='Specify user to run {0}.'.format(self.get_prog_name())
        )


class DaemonMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 30

    def _mixin_setup(self):
        self.add_option(
            '-d', '--daemon',
            default=False,
            action='store_true',
            help='Run the {0} as a daemon.'.format(self.get_prog_name())
        )
        self.add_option(
            '--pid-file', dest='pidfile',
            default=os.path.join(
                syspaths.PIDFILE_DIR, '{0}.pid'.format(self.get_prog_name())
            ),
            help="Specify the location of the pidfile. Default: '%default'."
        )

    def _mixin_before_exit(self):
        if hasattr(self, 'config') and self.config.get('pidfile'):
            # We've loaded and merged options into the configuration, it's safe
            # to query about the pidfile
            if self.check_pidfile():
                try:
                    os.unlink(self.config['pidfile'])
                except OSError as err:
                    # Log error only when running salt-master as a root user.
                    # Otherwise this can be ignored, since salt-master is able to
                    # overwrite the PIDfile on the next start.
                    err_msg = ('PIDfile could not be deleted: %s',
                               six.text_type(self.config['pidfile']))
                    if salt.utils.platform.is_windows():
                        user = salt.utils.win_functions.get_current_user()
                        if salt.utils.win_functions.is_admin(user):
                            logger.info(*err_msg)
                            logger.debug(six.text_type(err))
                    else:
                        if not os.getuid():
                            logger.info(*err_msg)
                            logger.debug(six.text_type(err))

    def set_pidfile(self):
        from salt.utils.process import set_pidfile
        set_pidfile(self.config['pidfile'], self.config['user'])

    def check_pidfile(self):
        '''
        Report whether a pidfile exists
        '''
        from salt.utils.process import check_pidfile
        return check_pidfile(self.config['pidfile'])

    def get_pidfile(self):
        '''
        Return a pid contained in a pidfile
        '''
        from salt.utils.process import get_pidfile
        return get_pidfile(self.config['pidfile'])

    def daemonize_if_required(self):
        if self.options.daemon:
            if self._setup_mp_logging_listener_ is True:
                # Stop the logging queue listener for the current process
                # We'll restart it once forked
                log.shutdown_multiprocessing_logging_listener(daemonizing=True)

            # Late import so logging works correctly
            salt.utils.process.daemonize()

        # Setup the multiprocessing log queue listener if enabled
        self._setup_mp_logging_listener()

    def check_running(self):
        '''
        Check if a pid file exists and if it is associated with
        a running process.
        '''

        if self.check_pidfile():
            pid = self.get_pidfile()
            if not salt.utils.platform.is_windows():
                if self.check_pidfile() and self.is_daemonized(pid) and os.getppid() != pid:
                    return True
            else:
                # We have no os.getppid() on Windows. Use salt.utils.win_functions.get_parent_pid
                if self.check_pidfile() and self.is_daemonized(pid) and salt.utils.win_functions.get_parent_pid() != pid:
                    return True
        return False

    def is_daemonized(self, pid):
        from salt.utils.process import os_is_running
        return os_is_running(pid)

    # Common methods for scripts which can daemonize
    def _install_signal_handlers(self):
        signal.signal(signal.SIGTERM, self._handle_signals)
        signal.signal(signal.SIGINT, self._handle_signals)

    def prepare(self):
        self.parse_args()

    def start(self):
        self.prepare()
        self._install_signal_handlers()

    def _handle_signals(self, signum, sigframe):  # pylint: disable=unused-argument
        msg = self.__class__.__name__
        if signum == signal.SIGINT:
            msg += ' received a SIGINT.'
        elif signum == signal.SIGTERM:
            msg += ' received a SIGTERM.'
        logging.getLogger(__name__).warning('%s Exiting.', msg)
        self.shutdown(exitmsg='{0} Exited.'.format(msg))

    def shutdown(self, exitcode=0, exitmsg=None):
        self.exit(exitcode, exitmsg)


class TargetOptionsMixIn(six.with_metaclass(MixInMeta, object)):

    _mixin_prio_ = 20

    selected_target_option = None

    def _mixin_setup(self):
        group = self.target_options_group = optparse.OptionGroup(
            self, 'Target Options', 'Target selection options.'
        )
        self.add_option_group(group)
        group.add_option(
            '-H', '--hosts',
            default=False,
            action='store_true',
            dest='list_hosts',
            help='List all known hosts to currently visible or other specified rosters'
        )
        group.add_option(
            '-E', '--pcre',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'servers, use pcre regular expressions.')
        )
        group.add_option(
            '-L', '--list',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'servers, take a comma or whitespace delimited list of '
                  'servers.')
        )
        group.add_option(
            '-G', '--grain',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a grain value to identify targets, the syntax '
                  'for the target is the grain key followed by a glob'
                  'expression: "os:Arch*".')
        )
        group.add_option(
            '-P', '--grain-pcre',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a grain value to identify targets, the syntax '
                  'for the target is the grain key followed by a pcre '
                  'regular expression: "os:Arch.*".')
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
                  'Range expressions look like %cluster.')
        )

        group = self.additional_target_options_group = optparse.OptionGroup(
            self,
            'Additional Target Options',
            'Additional options for minion targeting.'
        )
        self.add_option_group(group)
        group.add_option(
            '--delimiter',
            default=DEFAULT_TARGET_DELIM,
            help=('Change the default delimiter for matching in multi-level '
                  'data structures. Default: \'%default\'.')
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
        group_options_selected = [
            option for option in self.target_options_group.option_list if
            getattr(self.options, option.dest) is True
        ]
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
                  '\'G@os:RedHat and webser* or E@database.*\'.')
        )
        group.add_option(
            '-I', '--pillar',
            default=False,
            dest='pillar_target',
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a pillar value to identify targets, the syntax '
                  'for the target is the pillar key followed by a glob '
                  'expression: "role:production*".')
        )
        group.add_option(
            '-J', '--pillar-pcre',
            default=False,
            action='store_true',
            help=('Instead of using shell globs to evaluate the target '
                  'use a pillar value to identify targets, the syntax '
                  'for the target is the pillar key followed by a pcre '
                  'regular expression: "role:prod.*".')
        )
        group.add_option(
            '-S', '--ipcidr',
            default=False,
            action='store_true',
            help=('Match based on Subnet (CIDR notation) or IP address.')
        )

        self._create_process_functions()

    def process_pillar_target(self):
        if self.options.pillar_target:
            self.selected_target_option = 'pillar'


class TimeoutMixIn(six.with_metaclass(MixInMeta, object)):
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
                  'command (in seconds). Default: %default.')
        )


class ArgsStdinMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 10

    def _mixin_setup(self):
        self.add_option(
            '--args-stdin',
            default=False,
            dest='args_stdin',
            action='store_true',
            help=('Read additional options and/or arguments from stdin. '
                  'Each entry is newline separated.')
        )


class ProxyIdMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio = 40

    def _mixin_setup(self):
        self.add_option(
            '--proxyid',
            default=None,
            dest='proxyid',
            help=('Id for this proxy.')
        )


class ExecutorsMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio = 10

    def _mixin_setup(self):
        self.add_option(
            '--module-executors',
            dest='module_executors',
            default=None,
            metavar='EXECUTOR_LIST',
            help=('Set an alternative list of executors to override the one '
                  'set in minion config.')
        )
        self.add_option(
            '--executor-opts',
            dest='executor_opts',
            default=None,
            metavar='EXECUTOR_OPTS',
            help=('Set alternate executor options if supported by executor. '
                  'Options set by minion config are used by default.')
        )


class CacheDirMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio = 40

    def _mixin_setup(self):
        self.add_option(
            '--cachedir',
            default='/var/cache/salt/',
            dest='cachedir',
            help=('Cache Directory')
        )


class OutputOptionsMixIn(six.with_metaclass(MixInMeta, object)):

    _mixin_prio_ = 40
    _include_text_out_ = False

    selected_output_option = None

    def _mixin_setup(self):
        group = self.output_options_group = optparse.OptionGroup(
            self, 'Output Options', 'Configure your preferred output format.'
        )
        self.add_option_group(group)

        group.add_option(
            '--out', '--output',
            dest='output',
            help=(
                'Print the output from the \'{0}\' command using the '
                'specified outputter.'.format(
                    self.get_prog_name(),
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
            '--out-file', '--output-file',
            dest='output_file',
            default=None,
            help='Write the output to the specified file.'
        )
        group.add_option(
            '--out-file-append', '--output-file-append',
            action='store_true',
            dest='output_file_append',
            default=False,
            help='Append the output to the specified file.'
        )
        group.add_option(
            '--no-color', '--no-colour',
            default=False,
            action='store_true',
            help='Disable all colored output.'
        )
        group.add_option(
            '--force-color', '--force-colour',
            default=False,
            action='store_true',
            help='Force colored output.'
        )
        group.add_option(
            '--state-output', '--state_output',
            default=None,
            help=('Override the configured state_output value for minion '
                  'output. One of \'full\', \'terse\', \'mixed\', \'changes\' or \'filter\'. '
                  'Default: \'%default\'.')
        )
        group.add_option(
            '--state-verbose', '--state_verbose',
            default=None,
            help=('Override the configured state_verbose value for minion '
                  'output. Set to True or False. Default: %default.')
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

    def process_output_file(self):
        if self.options.output_file is not None and self.options.output_file_append is False:
            if os.path.isfile(self.options.output_file):
                try:
                    with salt.utils.files.fopen(self.options.output_file, 'w'):
                        # Make this a zero length filename instead of removing
                        # it. This way we keep the file permissions.
                        pass
                except (IOError, OSError) as exc:
                    self.error(
                        '{0}: Access denied: {1}'.format(
                            self.options.output_file,
                            exc
                        )
                    )

    def process_state_verbose(self):
        if self.options.state_verbose == "True" or self.options.state_verbose == "true":
            self.options.state_verbose = True
        elif self.options.state_verbose == "False" or self.options.state_verbose == "false":
            self.options.state_verbose = False

    def _mixin_after_parsed(self):
        group_options_selected = [
            option for option in self.output_options_group.option_list if (
                getattr(self.options, option.dest) and
                (option.dest.endswith('_out') or option.dest == 'output'))
        ]
        if len(group_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format('/'.join([
                    option.get_opt_string() for
                    option in group_options_selected
                ]))
            )
        self.config['selected_output_option'] = self.selected_output_option


class ExecutionOptionsMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 10

    def _mixin_setup(self):
        group = self.execution_group = optparse.OptionGroup(
            self,
            'Execution Options',
            # Include description here as a string
        )
        group.add_option(
            '-L', '--location',
            default=None,
            help='Specify which region to connect to.'
        )
        group.add_option(
            '-a', '--action',
            default=None,
            help='Perform an action that may be specific to this cloud '
                 'provider. This argument requires one or more instance '
                 'names to be specified.'
        )
        group.add_option(
            '-f', '--function',
            nargs=2,
            default=None,
            metavar='<FUNC-NAME> <PROVIDER>',
            help='Perform a function that may be specific to this cloud '
                 'provider, that does not apply to an instance. This '
                 'argument requires a provider to be specified (i.e.: nova).'
        )
        group.add_option(
            '-p', '--profile',
            default=None,
            help='Create an instance using the specified profile.'
        )
        group.add_option(
            '-m', '--map',
            default=None,
            help='Specify a cloud map file to use for deployment. This option '
                 'may be used alone, or in conjunction with -Q, -F, -S or -d. '
                 'The map can also be filtered by a list of VM names.'
        )
        group.add_option(
            '-H', '--hard',
            default=False,
            action='store_true',
            help='Delete all VMs that are not defined in the map file. '
                 'CAUTION!!! This operation can irrevocably destroy VMs! It '
                 'must be explicitly enabled in the cloud config file.'
        )
        group.add_option(
            '-d', '--destroy',
            default=False,
            action='store_true',
            help='Destroy the specified instance(s).'
        )
        group.add_option(
            '--no-deploy',
            default=True,
            dest='deploy',
            action='store_false',
            help='Don\'t run a deploy script after instance creation.'
        )
        group.add_option(
            '-P', '--parallel',
            default=False,
            action='store_true',
            help='Build all of the specified instances in parallel.'
        )
        group.add_option(
            '-u', '--update-bootstrap',
            default=False,
            action='store_true',
            help='Update salt-bootstrap to the latest stable bootstrap release.'
        )
        group.add_option(
            '-y', '--assume-yes',
            default=False,
            action='store_true',
            help='Default "yes" in answer to all confirmation questions.'
        )
        group.add_option(
            '-k', '--keep-tmp',
            default=False,
            action='store_true',
            help='Do not remove files from /tmp/ after deploy.sh finishes.'
        )
        group.add_option(
            '--show-deploy-args',
            default=False,
            action='store_true',
            help='Include the options used to deploy the minion in the data '
                 'returned.'
        )
        group.add_option(
            '--script-args',
            default=None,
            help='Script arguments to be fed to the bootstrap script when '
                 'deploying the VM.'
        )
        group.add_option(
            '-b', '--bootstrap',
            nargs=1,
            default=False,
            metavar='<HOST> [MINION_ID] [OPTIONS...]',
            help='Bootstrap an existing machine.'
        )
        self.add_option_group(group)

    def process_function(self):
        if self.options.function:
            self.function_name, self.function_provider = self.options.function
            if self.function_provider.startswith('-') or \
                    '=' in self.function_provider:
                self.error(
                    '--function expects two arguments: <function-name> '
                    '<provider>'
                )


class CloudQueriesMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 20

    selected_query_option = None

    def _mixin_setup(self):
        group = self.cloud_queries_group = optparse.OptionGroup(
            self,
            'Query Options',
            # Include description here as a string
        )
        group.add_option(
            '-Q', '--query',
            default=False,
            action='store_true',
            help=('Execute a query and return some information about the '
                  'nodes running on configured cloud providers.')
        )
        group.add_option(
            '-F', '--full-query',
            default=False,
            action='store_true',
            help=('Execute a query and return all information about the '
                  'nodes running on configured cloud providers.')
        )
        group.add_option(
            '-S', '--select-query',
            default=False,
            action='store_true',
            help=('Execute a query and return select information about '
                  'the nodes running on configured cloud providers.')
        )
        group.add_option(
            '--list-providers',
            default=False,
            action='store_true',
            help='Display a list of configured providers.'
        )
        group.add_option(
            '--list-profiles',
            default=None,
            action='store',
            help='Display a list of configured profiles. Pass in a cloud '
                 'provider to view the provider\'s associated profiles, '
                 'such as digitalocean, or pass in "all" to list all the '
                 'configured profiles.'
        )
        self.add_option_group(group)
        self._create_process_functions()

    def _create_process_functions(self):
        for option in self.cloud_queries_group.option_list:
            def process(opt):
                if getattr(self.options, opt.dest):
                    query = 'list_nodes'
                    if opt.dest == 'full_query':
                        query += '_full'
                    elif opt.dest == 'select_query':
                        query += '_select'
                    elif opt.dest == 'list_providers':
                        query = 'list_providers'
                        if self.args:
                            self.error(
                                '\'--list-providers\' does not accept any '
                                'arguments'
                            )
                    elif opt.dest == 'list_profiles':
                        query = 'list_profiles'
                        option_dict = vars(self.options)
                        if option_dict.get('list_profiles') == '--list-providers':
                            self.error(
                                '\'--list-profiles\' does not accept '
                                '\'--list-providers\' as an argument'
                            )
                    self.selected_query_option = query

            funcname = 'process_{0}'.format(option.dest)
            if not hasattr(self, funcname):
                setattr(self, funcname, partial(process, option))

    def _mixin_after_parsed(self):
        group_options_selected = [
            option for option in self.cloud_queries_group.option_list if
            getattr(self.options, option.dest) is not False and
            getattr(self.options, option.dest) is not None
        ]
        if len(group_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format('/'.join([
                    option.get_opt_string() for option in
                    group_options_selected
                ]))
            )
        self.config['selected_query_option'] = self.selected_query_option


class CloudProvidersListsMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 30

    def _mixin_setup(self):
        group = self.providers_listings_group = optparse.OptionGroup(
            self,
            'Cloud Providers Listings',
            # Include description here as a string
        )
        group.add_option(
            '--list-locations',
            default=None,
            help=('Display a list of locations available in configured cloud '
                  'providers. Pass the cloud provider that available '
                  'locations are desired on, aka "linode", or pass "all" to '
                  'list locations for all configured cloud providers.')
        )
        group.add_option(
            '--list-images',
            default=None,
            help=('Display a list of images available in configured cloud '
                  'providers. Pass the cloud provider that available images '
                  'are desired on, aka "linode", or pass "all" to list images '
                  'for all configured cloud providers.')
        )
        group.add_option(
            '--list-sizes',
            default=None,
            help=('Display a list of sizes available in configured cloud '
                  'providers. Pass the cloud provider that available sizes '
                  'are desired on, aka "AWS", or pass "all" to list sizes '
                  'for all configured cloud providers.')
        )
        self.add_option_group(group)

    def _mixin_after_parsed(self):
        list_options_selected = [
            option for option in self.providers_listings_group.option_list if
            getattr(self.options, option.dest) is not None
        ]
        if len(list_options_selected) > 1:
            self.error(
                'The options {0} are mutually exclusive. Please only choose '
                'one of them'.format(
                    '/'.join([
                        option.get_opt_string() for option in
                        list_options_selected
                    ])
                )
            )


class ProfilingPMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 130

    def _mixin_setup(self):
        group = self.profiling_group = optparse.OptionGroup(
            self,
            'Profiling support',
            # Include description here as a string
        )

        group.add_option(
            '--profiling-path',
            dest='profiling_path',
            default='/tmp/stats',
            help=('Folder that will hold all stats generations path. Default: \'%default\'.')
        )
        group.add_option(
            '--enable-profiling',
            dest='profiling_enabled',
            default=False,
            action='store_true',
            help=('Enable generating profiling stats. See also: --profiling-path.')
        )
        self.add_option_group(group)


class CloudCredentialsMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 30

    def _mixin_setup(self):
        group = self.cloud_credentials_group = optparse.OptionGroup(
            self,
            'Cloud Credentials',
            # Include description here as a string
        )
        group.add_option(
            '--set-password',
            default=None,
            nargs=2,
            metavar='<USERNAME> <PROVIDER>',
            help=('Configure password for a cloud provider and save it to the keyring. '
                  'PROVIDER can be specified with or without a driver, for example: '
                  '"--set-password bob rackspace" or more specific '
                  '"--set-password bob rackspace:openstack" '
                  'Deprecated.')
        )
        self.add_option_group(group)

    def process_set_password(self):
        if self.options.set_password:
            raise RuntimeError(
                'This functionality is not supported; '
                'please see the keyring module at http://docs.saltstack.com/en/latest/topics/sdb/'
            )


class EAuthMixIn(six.with_metaclass(MixInMeta, object)):
    _mixin_prio_ = 30

    def _mixin_setup(self):
        group = self.eauth_group = optparse.OptionGroup(
            self,
            'External Authentication',
            # Include description here as a string
        )
        group.add_option(
            '-a', '--auth', '--eauth', '--external-auth',
            default='',
            dest='eauth',
            help=('Specify an external authentication system to use.')
        )
        group.add_option(
            '-T', '--make-token',
            default=False,
            dest='mktoken',
            action='store_true',
            help=('Generate and save an authentication token for re-use. The '
                  'token is generated and made available for the period '
                  'defined in the Salt Master.')
        )
        group.add_option(
            '--username',
            dest='username',
            nargs=1,
            help=('Username for external authentication.')
        )
        group.add_option(
            '--password',
            dest='password',
            nargs=1,
            help=('Password for external authentication.')
        )
        self.add_option_group(group)


class MasterOptionParser(six.with_metaclass(OptionParserMeta,
                                            OptionParser,
                                            ConfigDirMixIn,
                                            MergeConfigMixIn,
                                            LogLevelMixIn,
                                            RunUserMixin,
                                            DaemonMixIn,
                                            SaltfileMixIn)):

    description = 'The Salt Master, used to control the Salt Minions'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS['log_file']
    _setup_mp_logging_listener_ = True

    def setup_config(self):
        return config.master_config(self.get_config_file_path())


class MinionOptionParser(six.with_metaclass(OptionParserMeta,
                                            MasterOptionParser)):  # pylint: disable=no-init

    description = (
        'The Salt Minion, receives commands from a remote Salt Master'
    )

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'minion'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = config.DEFAULT_MINION_OPTS['log_file']
    _setup_mp_logging_listener_ = True

    def setup_config(self):
        opts = config.minion_config(self.get_config_file_path(),  # pylint: disable=no-member
                                    cache_minion_id=True,
                                    ignore_config_errors=False)
        # Optimization: disable multiprocessing logging if running as a
        #               daemon, without engines and without multiprocessing
        if not opts.get('engines') and not opts.get('multiprocessing', True) \
                and self.options.daemon:  # pylint: disable=no-member
            self._setup_mp_logging_listener_ = False
        return opts


class ProxyMinionOptionParser(six.with_metaclass(OptionParserMeta,
                                                 OptionParser,
                                                 ProxyIdMixIn,
                                                 ConfigDirMixIn,
                                                 MergeConfigMixIn,
                                                 LogLevelMixIn,
                                                 RunUserMixin,
                                                 DaemonMixIn,
                                                 SaltfileMixIn)):  # pylint: disable=no-init

    description = (
        'The Salt Proxy Minion, connects to and controls devices not able to run a minion.\n'
        'Receives commands from a remote Salt Master.'
    )

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'proxy'
    # LogLevelMixIn attributes
    _default_logging_logfile_ = config.DEFAULT_PROXY_MINION_OPTS['log_file']

    def setup_config(self):
        try:
            minion_id = self.values.proxyid
        except AttributeError:
            minion_id = None

        return config.proxy_config(self.get_config_file_path(),
                                    cache_minion_id=False,
                                    minion_id=minion_id)


class SyndicOptionParser(six.with_metaclass(OptionParserMeta,
                                            OptionParser,
                                            ConfigDirMixIn,
                                            MergeConfigMixIn,
                                            LogLevelMixIn,
                                            RunUserMixin,
                                            DaemonMixIn,
                                            SaltfileMixIn)):

    description = (
        'The Salt Syndic daemon, a special Minion that passes through commands from a\n'
        'higher Master. Scale Salt to thousands of hosts or across many different networks.'
    )

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _logfile_config_setting_name_ = 'syndic_log_file'
    _default_logging_level_ = config.DEFAULT_MASTER_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS[_logfile_config_setting_name_]
    _setup_mp_logging_listener_ = True

    def setup_config(self):
        return config.syndic_config(
            self.get_config_file_path(),
            self.get_config_file_path('minion'))


class SaltSupportOptionParser(six.with_metaclass(OptionParserMeta, OptionParser, ConfigDirMixIn,
                                                 MergeConfigMixIn, LogLevelMixIn, TimeoutMixIn)):
    default_timeout = 5
    description = 'Salt Support is a program to collect all support data: logs, system configuration etc.'
    usage = '%prog [options] \'<target>\' <function> [arguments]'
    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _default_logging_level_ = config.DEFAULT_MASTER_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS['log_file']

    def _mixin_setup(self):
        self.add_option('-P', '--show-profiles', default=False, action='store_true',
                        dest='support_profile_list', help='Show available profiles')
        self.add_option('-p', '--profile', default='', dest='support_profile',
                        help='Specify support profile or comma-separated profiles, e.g.: "salt,network"')
        support_archive = '{t}/{h}-support.tar.bz2'.format(t=tempfile.gettempdir(),
                                                           h=salt.utils.network.get_fqhostname())
        self.add_option('-a', '--archive', default=support_archive, dest='support_archive',
                        help=('Specify name of the resulting support archive. '
                              'Default is "{f}".'.format(f=support_archive)))
        self.add_option('-u', '--unit', default='', dest='support_unit',
                        help='Specify examined unit (default "master").')
        self.add_option('-U', '--show-units', default=False, action='store_true', dest='support_show_units',
                        help='Show available units')
        self.add_option('-f', '--force', default=False, action='store_true', dest='support_archive_force_overwrite',
                        help='Force overwrite existing archive, if exists')
        self.add_option('-o', '--out', default='null', dest='support_output_format',
                        help=('Set the default output using the specified outputter, '
                              'unless profile does not overrides this. Default: "yaml".'))

    def find_existing_configs(self, default):
        '''
        Find configuration files on the system.
        :return:
        '''
        configs = []
        for cfg in [default, self._config_filename_, 'minion', 'proxy', 'cloud', 'spm']:
            if not cfg:
                continue
            config_path = self.get_config_file_path(cfg)
            if os.path.exists(config_path):
                configs.append(cfg)

        if default and default not in configs:
            raise SystemExit('Unknown configuration unit: {}'.format(default))

        return configs

    def setup_config(self, cfg=None):
        '''
        Open suitable config file.
        :return:
        '''
        _opts, _args = optparse.OptionParser.parse_args(self)
        configs = self.find_existing_configs(_opts.support_unit)
        if configs and cfg not in configs:
            cfg = configs[0]

        return config.master_config(self.get_config_file_path(cfg))


class SaltCMDOptionParser(six.with_metaclass(OptionParserMeta,
                                             OptionParser,
                                             ConfigDirMixIn,
                                             MergeConfigMixIn,
                                             TimeoutMixIn,
                                             ExtendedTargetOptionsMixIn,
                                             OutputOptionsMixIn,
                                             LogLevelMixIn,
                                             ExecutorsMixIn,
                                             HardCrashMixin,
                                             SaltfileMixIn,
                                             ArgsStdinMixIn,
                                             EAuthMixIn,
                                             NoParseMixin)):

    default_timeout = 5

    description = (
        'Salt allows for commands to be executed across a swath of remote systems in\n'
        'parallel, so they can be both controlled and queried with ease.'
    )

    usage = '%prog [options] \'<target>\' <function> [arguments]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _default_logging_level_ = config.DEFAULT_MASTER_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS['log_file']

    try:
        os.getcwd()
    except OSError:
        sys.exit("Cannot access current working directory. Exiting!")

    def _mixin_setup(self):
        self.add_option(
            '-s', '--static',
            default=False,
            action='store_true',
            help=('Return the data from minions as a group after they '
                  'all return.')
        )
        self.add_option(
            '-p', '--progress',
            default=False,
            action='store_true',
            help=('Display a progress graph. Requires "progressbar" python package.')
        )
        self.add_option(
            '--failhard',
            default=False,
            action='store_true',
            help=('Stop batch execution upon first "bad" return.')
        )
        self.add_option(
            '--async',
            default=False,
            dest='async',
            action='store_true',
            help=('Run the salt command but don\'t wait for a reply.')
        )
        self.add_option(
            '--subset',
            default=0,
            type=int,
            help=('Execute the routine on a random subset of the targeted '
                  'minions. The minions will be verified that they have the '
                  'named function before executing.')
        )
        self.add_option(
            '-v', '--verbose',
            default=False,
            action='store_true',
            help=('Turn on command verbosity, display jid and active job '
                  'queries.')
        )
        self.add_option(
            '--hide-timeout',
            dest='show_timeout',
            default=True,
            action='store_false',
            help=('Hide minions that timeout.')
        )
        self.add_option(
            '--show-jid',
            default=False,
            action='store_true',
            help=('Display jid without the additional output of --verbose.')
        )
        self.add_option(
            '-b', '--batch',
            '--batch-size',
            default='',
            dest='batch',
            help=('Execute the salt job in batch mode, pass either the number '
                  'of minions to batch at a time, or the percentage of '
                  'minions to have running.')
        )
        self.add_option(
            '--batch-wait',
            default=0,
            dest='batch_wait',
            type=float,
            help=('Wait the specified time in seconds after each job is done '
                  'before freeing the slot in the batch for the next one.')
        )
        self.add_option(
            '--batch-safe-limit',
            default=0,
            dest='batch_safe_limit',
            type=int,
            help=('Execute the salt job in batch mode if the job would have '
                  'executed on more than this many minions.')
        )
        self.add_option(
            '--batch-safe-size',
            default=8,
            dest='batch_safe_size',
            help=('Batch size to use for batch jobs created by batch-safe-limit.')
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
            '--return_config',
            default='',
            metavar='RETURNER_CONF',
            help=('Set an alternative return method. By default salt will '
                  'send the return data from the command back to the master, '
                  'but the return data can be redirected into any number of '
                  'systems, databases or applications.')
        )
        self.add_option(
            '--return_kwargs',
            default={},
            metavar='RETURNER_KWARGS',
            help=('Set any returner options at the command line.')
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
        self.add_option(
            '--summary',
            dest='cli_summary',
            default=False,
            action='store_true',
            help=('Display summary information about a salt command.')
        )
        self.add_option(
            '--metadata',
            default='',
            metavar='METADATA',
            help=('Pass metadata into Salt, used to search jobs.')
        )
        self.add_option(
            '--output-diff',
            dest='state_output_diff',
            action='store_true',
            default=False,
            help=('Report only those states that have changed.')
        )
        self.add_option(
            '--config-dump',
            dest='config_dump',
            action='store_true',
            default=False,
            help=('Dump the master configuration values')
        )
        self.add_option(
            '--preview-target',
            dest='preview_target',
            action='store_true',
            default=False,
            help=('Show the minions expected to match a target. Does not issue any command.')
        )

    def _mixin_after_parsed(self):
        if len(self.args) <= 1 and not self.options.doc and not self.options.preview_target:
            try:
                self.print_help()
            except Exception:  # pylint: disable=broad-except
                # We get an argument that Python's optparser just can't deal
                # with. Perhaps stdout was redirected, or a file glob was
                # passed in. Regardless, we're in an unknown state here.
                sys.stdout.write('Invalid options passed. Please try -h for '
                                 'help.')  # Try to warn if we can.
                sys.exit(salt.defaults.exitcodes.EX_GENERIC)

        # Dump the master configuration file, exit normally at the end.
        if self.options.config_dump:
            cfg = config.master_config(self.get_config_file_path())
            sys.stdout.write(
                salt.utils.yaml.safe_dump(
                    cfg,
                    default_flow_style=False)
            )
            sys.exit(salt.defaults.exitcodes.EX_OK)

        if self.options.preview_target:
            # Insert dummy arg which won't be used
            self.args.append('not_a_valid_command')

        if self.options.doc:
            # Include the target
            if not self.args:
                self.args.insert(0, '*')
            if len(self.args) < 2:
                # Include the function
                self.args.insert(1, 'sys.doc')
            if self.args[1] != 'sys.doc':
                self.args.insert(1, 'sys.doc')
            if len(self.args) > 3:
                self.error('You can only get documentation for one method at one time.')

        if self.options.list:
            try:
                if ',' in self.args[0]:
                    self.config['tgt'] = self.args[0].replace(' ', '').split(',')
                else:
                    self.config['tgt'] = self.args[0].split()
            except IndexError:
                self.exit(42, '\nCannot execute command without defining a target.\n\n')
        else:
            try:
                self.config['tgt'] = self.args[0]
            except IndexError:
                self.exit(42, '\nCannot execute command without defining a target.\n\n')
        # Detect compound command and set up the data for it
        if self.args:
            try:
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
                        if len(self.config['fun']) > len(self.config['arg']):
                            self.exit(42, 'Cannot execute compound command without '
                                          'defining all arguments.\n')
                        elif len(self.config['fun']) < len(self.config['arg']):
                            self.exit(42, 'Cannot execute compound command with more '
                                          'arguments than commands.\n')
                    # parse the args and kwargs before sending to the publish
                    # interface
                    for i in range(len(self.config['arg'])):
                        self.config['arg'][i] = salt.utils.args.parse_input(
                            self.config['arg'][i],
                            no_parse=self.options.no_parse)
                else:
                    self.config['fun'] = self.args[1]
                    self.config['arg'] = self.args[2:]
                    # parse the args and kwargs before sending to the publish
                    # interface
                    self.config['arg'] = salt.utils.args.parse_input(
                        self.config['arg'],
                        no_parse=self.options.no_parse)
            except IndexError:
                self.exit(42, '\nIncomplete options passed.\n\n')

    def setup_config(self):
        return config.client_config(self.get_config_file_path())


class SaltCPOptionParser(six.with_metaclass(OptionParserMeta,
                                            OptionParser,
                                            OutputOptionsMixIn,
                                            ConfigDirMixIn,
                                            MergeConfigMixIn,
                                            TimeoutMixIn,
                                            TargetOptionsMixIn,
                                            LogLevelMixIn,
                                            HardCrashMixin,
                                            SaltfileMixIn)):
    description = (
        'salt-cp is NOT intended to broadcast large files, it is intended to handle text\n'
        'files. salt-cp can be used to distribute configuration files.'
    )

    usage = '%prog [options] \'<target>\' SOURCE DEST'

    default_timeout = 5

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _default_logging_level_ = config.DEFAULT_MASTER_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS['log_file']

    def _mixin_setup(self):
        file_opts_group = optparse.OptionGroup(self, 'File Options')
        file_opts_group.add_option(
            '-C', '--chunked',
            default=False,
            dest='chunked',
            action='store_true',
            help='Use chunked files transfer. Supports big files, recursive '
                 'lookup and directories creation.'
        )
        file_opts_group.add_option(
            '-n', '--no-compression',
            default=True,
            dest='gzip',
            action='store_false',
            help='Disable gzip compression.'
        )
        self.add_option_group(file_opts_group)

    def _mixin_after_parsed(self):
        # salt-cp needs arguments
        if len(self.args) <= 1:
            self.print_help()
            self.error('Insufficient arguments')

        if self.options.list:
            if ',' in self.args[0]:
                self.config['tgt'] = self.args[0].split(',')
            else:
                self.config['tgt'] = self.args[0].split()
        else:
            self.config['tgt'] = self.args[0]
        self.config['src'] = [os.path.realpath(x) for x in self.args[1:-1]]
        self.config['dest'] = self.args[-1]

    def setup_config(self):
        return config.master_config(self.get_config_file_path())


class SaltKeyOptionParser(six.with_metaclass(OptionParserMeta,
                                             OptionParser,
                                             ConfigDirMixIn,
                                             MergeConfigMixIn,
                                             LogLevelMixIn,
                                             OutputOptionsMixIn,
                                             RunUserMixin,
                                             HardCrashMixin,
                                             SaltfileMixIn,
                                             EAuthMixIn)):

    description = 'salt-key is used to manage Salt authentication keys'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _skip_console_logging_config_ = True
    _logfile_config_setting_name_ = 'key_logfile'
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS[_logfile_config_setting_name_]

    def _mixin_setup(self):
        actions_group = optparse.OptionGroup(self, 'Actions')
        actions_group.set_conflict_handler('resolve')
        actions_group.add_option(
            '-l', '--list',
            default='',
            metavar='ARG',
            help=('List the public keys. The args '
                  '\'pre\', \'un\', and \'unaccepted\' will list '
                  'unaccepted/unsigned keys. '
                  '\'acc\' or \'accepted\' will list accepted/signed keys. '
                  '\'rej\' or \'rejected\' will list rejected keys. '
                  '\'den\' or \'denied\' will list denied keys. '
                  'Finally, \'all\' will list all keys.')
        )

        actions_group.add_option(
            '-L', '--list-all',
            default=False,
            action='store_true',
            help='List all public keys. Deprecated: use "--list all".'
        )

        actions_group.add_option(
            '-a', '--accept',
            default='',
            help='Accept the specified public key (use --include-rejected and '
                 '--include-denied to match rejected and denied keys in '
                 'addition to pending keys). Globs are supported.',
        )

        actions_group.add_option(
            '-A', '--accept-all',
            default=False,
            action='store_true',
            help='Accept all pending keys.'
        )

        actions_group.add_option(
            '-r', '--reject',
            default='',
            help='Reject the specified public key. Use --include-accepted and '
                 '--include-denied to match accepted and denied keys in '
                 'addition to pending keys. Globs are supported.'
        )

        actions_group.add_option(
            '-R', '--reject-all',
            default=False,
            action='store_true',
            help='Reject all pending keys.'
        )

        actions_group.add_option(
            '--include-all',
            default=False,
            action='store_true',
            help='Include rejected/accepted keys when accepting/rejecting. '
                 'Deprecated: use "--include-rejected" and "--include-accepted".'
        )

        actions_group.add_option(
            '--include-accepted',
            default=False,
            action='store_true',
            help='Include accepted keys when rejecting.'
        )

        actions_group.add_option(
            '--include-rejected',
            default=False,
            action='store_true',
            help='Include rejected keys when accepting.'
        )

        actions_group.add_option(
            '--include-denied',
            default=False,
            action='store_true',
            help='Include denied keys when accepting/rejecting.'
        )

        actions_group.add_option(
            '-p', '--print',
            default='',
            help='Print the specified public key.'
        )

        actions_group.add_option(
            '-P', '--print-all',
            default=False,
            action='store_true',
            help='Print all public keys.'
        )

        actions_group.add_option(
            '-d', '--delete',
            default='',
            help='Delete the specified key. Globs are supported.'
        )

        actions_group.add_option(
            '-D', '--delete-all',
            default=False,
            action='store_true',
            help='Delete all keys.'
        )

        actions_group.add_option(
            '-f', '--finger',
            default='',
            help='Print the specified key\'s fingerprint.'
        )

        actions_group.add_option(
            '-F', '--finger-all',
            default=False,
            action='store_true',
            help='Print all keys\' fingerprints.'
        )
        self.add_option_group(actions_group)

        self.add_option(
            '-q', '--quiet',
            default=False,
            action='store_true',
            help='Suppress output.'
        )

        self.add_option(
            '-y', '--yes',
            default=False,
            action='store_true',
            help='Answer "Yes" to all questions presented. Default: %default.'
        )

        self.add_option(
            '--rotate-aes-key',
            default=True,
            help=('Setting this to False prevents the master from refreshing '
                  'the key session when keys are deleted or rejected, this '
                  'lowers the security of the key deletion/rejection operation. '
                  'Default: %default.')
        )

        self.add_option(
            '--preserve-minions',
            default=False,
            help=('Setting this to True prevents the master from deleting '
                  'the minion cache when keys are deleted, this may have '
                  'security implications if compromised minions auth with '
                  'a previous deleted minion ID. '
                  'Default: %default.')
        )

        key_options_group = optparse.OptionGroup(
            self, 'Key Generation Options'
        )
        self.add_option_group(key_options_group)
        key_options_group.add_option(
            '--gen-keys',
            default='',
            help='Set a name to generate a keypair for use with salt.'
        )

        key_options_group.add_option(
            '--gen-keys-dir',
            default='.',
            help=('Set the directory to save the generated keypair, only '
                  'works with "gen_keys_dir" option. Default: \'%default\'.')
        )

        key_options_group.add_option(
            '--keysize',
            default=2048,
            type=int,
            help=('Set the keysize for the generated key, only works with '
                  'the "--gen-keys" option, the key size must be 2048 or '
                  'higher, otherwise it will be rounded up to 2048. '
                  'Default: %default.')
        )

        key_options_group.add_option(
            '--gen-signature',
            default=False,
            action='store_true',
            help=('Create a signature file of the masters public-key named '
                  'master_pubkey_signature. The signature can be send to a '
                  'minion in the masters auth-reply and enables the minion '
                  'to verify the masters public-key cryptographically. '
                  'This requires a new signing-key-pair which can be auto-created '
                  'with the --auto-create parameter.')
        )

        key_options_group.add_option(
            '--priv',
            default='',
            type=str,
            help=('The private-key file to create a signature with.')
        )

        key_options_group.add_option(
            '--signature-path',
            default='',
            type=str,
            help=('The path where the signature file should be written.')
        )

        key_options_group.add_option(
            '--pub',
            default='',
            type=str,
            help=('The public-key file to create a signature for.')
        )

        key_options_group.add_option(
            '--auto-create',
            default=False,
            action='store_true',
            help=('Auto-create a signing key-pair if it does not yet exist.')
        )

    def process_config_dir(self):
        if self.options.gen_keys:
            # We're generating keys, override the default behavior of this
            # function if we don't have any access to the configuration
            # directory.
            if not os.access(self.options.config_dir, os.R_OK):
                if not os.path.isdir(self.options.gen_keys_dir):
                    # This would be done at a latter stage, but we need it now
                    # so no errors are thrown
                    os.makedirs(self.options.gen_keys_dir)
                self.options.config_dir = self.options.gen_keys_dir
        super(SaltKeyOptionParser, self).process_config_dir()
    # Don't change its mixin priority!
    process_config_dir._mixin_prio_ = ConfigDirMixIn._mixin_prio_

    def setup_config(self):
        keys_config = config.client_config(self.get_config_file_path())
        if self.options.gen_keys:
            # Since we're generating the keys, some defaults can be assumed
            # or tweaked
            keys_config[self._logfile_config_setting_name_] = os.devnull
            keys_config['pki_dir'] = self.options.gen_keys_dir

        return keys_config

    def process_rotate_aes_key(self):
        if hasattr(self.options, 'rotate_aes_key') and isinstance(self.options.rotate_aes_key, six.string_types):
            if self.options.rotate_aes_key.lower() == 'true':
                self.options.rotate_aes_key = True
            elif self.options.rotate_aes_key.lower() == 'false':
                self.options.rotate_aes_key = False

    def process_preserve_minions(self):
        if hasattr(self.options, 'preserve_minions') and isinstance(self.options.preserve_minions, six.string_types):
            if self.options.preserve_minions.lower() == 'true':
                self.options.preserve_minions = True
            elif self.options.preserve_minions.lower() == 'false':
                self.options.preserve_minions = False

    def process_list(self):
        # Filter accepted list arguments as soon as possible
        if not self.options.list:
            return
        if not self.options.list.startswith(('acc', 'pre', 'un', 'rej', 'den', 'all')):
            self.error(
                '\'{0}\' is not a valid argument to \'--list\''.format(
                    self.options.list
                )
            )

    def process_keysize(self):
        if self.options.keysize < 2048:
            self.error('The minimum value for keysize is 2048')
        elif self.options.keysize > 32768:
            self.error('The maximum value for keysize is 32768')

    def process_gen_keys_dir(self):
        # Schedule __create_keys_dir() to run if there's a value for
        # --create-keys-dir
        self._mixin_after_parsed_funcs.append(self.__create_keys_dir)  # pylint: disable=no-member

    def _mixin_after_parsed(self):
        # It was decided to always set this to info, since it really all is
        # info or error.
        self.config['loglevel'] = 'info'

    def __create_keys_dir(self, *args):  # pylint: disable=unused-argument
        if not os.path.isdir(self.config['gen_keys_dir']):
            os.makedirs(self.config['gen_keys_dir'])


class SaltCallOptionParser(six.with_metaclass(OptionParserMeta,
                                              OptionParser,
                                              ProxyIdMixIn,
                                              ConfigDirMixIn,
                                              ExecutorsMixIn,
                                              MergeConfigMixIn,
                                              LogLevelMixIn,
                                              OutputOptionsMixIn,
                                              HardCrashMixin,
                                              SaltfileMixIn,
                                              ArgsStdinMixIn,
                                              ProfilingPMixIn,
                                              NoParseMixin,
                                              CacheDirMixIn)):

    description = (
        'salt-call is used to execute module functions locally on a Salt Minion'
    )

    usage = '%prog [options] <function> [arguments]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'minion'

    # LogLevelMixIn attributes
    _default_logging_level_ = config.DEFAULT_MINION_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MINION_OPTS['log_file']

    def _mixin_setup(self):
        self.add_option(
            '-g', '--grains',
            dest='grains_run',
            default=False,
            action='store_true',
            help='Return the information generated by the salt grains.'
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
        self.add_option(
            '--file-root',
            default=None,
            help='Set this directory as the base file root.'
        )
        self.add_option(
            '--pillar-root',
            default=None,
            help='Set this directory as the base pillar root.'
        )
        self.add_option(
            '--states-dir',
            default=None,
            help='Set this directory to search for additional states.'
        )
        self.add_option(
            '--retcode-passthrough',
            default=False,
            action='store_true',
            help=('Exit with the salt call retcode and not the salt binary '
                  'retcode.')
        )
        self.add_option(
            '--metadata',
            default=False,
            dest='print_metadata',
            action='store_true',
            help=('Print out the execution metadata as well as the return. '
                  'This will print out the outputter data, the return code, '
                  'etc.')
        )
        self.add_option(
            '--set-metadata',
            dest='metadata',
            default=None,
            metavar='METADATA',
            help=('Pass metadata into Salt, used to search jobs.')
        )
        self.add_option(
            '--id',
            default='',
            dest='id',
            help=('Specify the minion id to use. If this option is omitted, '
                  'the id option from the minion config will be used.')
        )
        self.add_option(
            '--skip-grains',
            default=False,
            action='store_true',
            help=('Do not load grains.')
        )
        self.add_option(
            '--refresh-grains-cache',
            default=False,
            action='store_true',
            help=('Force a refresh of the grains cache.')
        )
        self.add_option(
            '-t', '--timeout',
            default=60,
            dest='auth_timeout',
            type=int,
            help=('Change the timeout, if applicable, for the running '
                  'command. Default: %default.')
        )
        self.add_option(
            '--output-diff',
            dest='state_output_diff',
            action='store_true',
            default=False,
            help=('Report only those states that have changed.')
        )

    def _mixin_after_parsed(self):
        if not self.args and not self.options.grains_run and not self.options.doc:
            self.print_help()
            self.error('Requires function, --grains or --doc')

        elif len(self.args) >= 1:
            if self.options.grains_run:
                self.error('-g/--grains does not accept any arguments')

            if self.options.doc and len(self.args) > 1:
                self.error('You can only get documentation for one method at one time')

            self.config['fun'] = self.args[0]
            self.config['arg'] = self.args[1:]

    def setup_config(self):
        if self.options.proxyid:
            opts = config.proxy_config(self.get_config_file_path(configfile='proxy'),
                                       cache_minion_id=True,
                                       minion_id=self.options.proxyid)
        else:
            opts = config.minion_config(self.get_config_file_path(),
                                        cache_minion_id=True)
        return opts

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


class SaltRunOptionParser(six.with_metaclass(OptionParserMeta,
                                             OptionParser,
                                             ConfigDirMixIn,
                                             MergeConfigMixIn,
                                             TimeoutMixIn,
                                             LogLevelMixIn,
                                             HardCrashMixin,
                                             SaltfileMixIn,
                                             OutputOptionsMixIn,
                                             ArgsStdinMixIn,
                                             ProfilingPMixIn,
                                             EAuthMixIn,
                                             NoParseMixin)):

    default_timeout = 1

    description = (
        'salt-run is the frontend command for executing Salt Runners.\n'
        'Salt Runners are modules used to execute convenience functions on the Salt Master'
    )

    usage = '%prog [options] <function> [arguments]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _default_logging_level_ = config.DEFAULT_MASTER_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS['log_file']

    def _mixin_setup(self):
        self.add_option(
            '-d', '--doc', '--documentation',
            dest='doc',
            default=False,
            action='store_true',
            help=('Display documentation for runners, pass a runner or '
                  'runner.function to see documentation on only that runner '
                  'or function.')
        )
        self.add_option(
            '--async',
            default=False,
            action='store_true',
            help='Start the runner operation and immediately return control.'
        )
        self.add_option(
            '--skip-grains',
            default=False,
            action='store_true',
            help='Do not load grains.'
        )
        group = self.output_options_group = optparse.OptionGroup(
            self, 'Output Options', 'Configure your preferred output format.'
        )
        self.add_option_group(group)

        group.add_option(
            '--quiet',
            default=False,
            action='store_true',
            help='Do not display the results of the run.'
        )

    def _mixin_after_parsed(self):
        if self.options.doc and len(self.args) > 1:
            self.error('You can only get documentation for one method at one time')

        if self.args:
            self.config['fun'] = self.args[0]
        else:
            self.config['fun'] = ''
        if len(self.args) > 1:
            self.config['arg'] = self.args[1:]
        else:
            self.config['arg'] = []

    def setup_config(self):
        return config.client_config(self.get_config_file_path())


class SaltSSHOptionParser(six.with_metaclass(OptionParserMeta,
                                             OptionParser,
                                             ConfigDirMixIn,
                                             MergeConfigMixIn,
                                             LogLevelMixIn,
                                             TargetOptionsMixIn,
                                             OutputOptionsMixIn,
                                             SaltfileMixIn,
                                             HardCrashMixin,
                                             CacheDirMixIn,
                                             NoParseMixin)):

    usage = '%prog [options] \'<target>\' <function> [arguments]'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'

    # LogLevelMixIn attributes
    _logfile_config_setting_name_ = 'ssh_log_file'
    _default_logging_level_ = config.DEFAULT_MASTER_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_MASTER_OPTS[_logfile_config_setting_name_]

    def _mixin_setup(self):
        self.add_option(
            '-r', '--raw', '--raw-shell',
            dest='raw_shell',
            default=False,
            action='store_true',
            help=('Don\'t execute a salt routine on the targets, execute a '
                  'raw shell command.')
        )
        self.add_option(
            '--roster',
            dest='roster',
            default='flat',
            help=('Define which roster system to use, this defines if a '
                  'database backend, scanner, or custom roster system is '
                  'used. Default: \'flat\'.')
        )
        self.add_option(
            '--roster-file',
            dest='roster_file',
            default='',
            help=('Define an alternative location for the default roster '
                  'file location. The default roster file is called roster '
                  'and is found in the same directory as the master config '
                  'file.')
        )
        self.add_option(
            '--refresh', '--refresh-cache',
            dest='refresh_cache',
            default=False,
            action='store_true',
            help=('Force a refresh of the master side data cache of the '
                  'target\'s data. This is needed if a target\'s grains have '
                  'been changed and the auto refresh timeframe has not been '
                  'reached.')
        )
        self.add_option(
            '--max-procs',
            dest='ssh_max_procs',
            default=25,
            type=int,
            help='Set the number of concurrent minions to communicate with. '
                 'This value defines how many processes are opened up at a '
                 'time to manage connections, the more running processes the '
                 'faster communication should be. Default: %default.'
        )
        self.add_option(
            '--extra-filerefs',
            dest='extra_filerefs',
            default=None,
            help='Pass in extra files to include in the state tarball.'
        )
        self.add_option('--min-extra-modules',
                        dest='min_extra_mods', default=None,
                        help='One or comma-separated list of extra Python modules'
                             'to be included into Minimal Salt.')
        self.add_option(
            '--thin-extra-modules',
            dest='thin_extra_mods',
            default=None,
            help='One or comma-separated list of extra Python modules'
                 'to be included into Thin Salt.')
        self.add_option(
            '-v', '--verbose',
            default=False,
            action='store_true',
            help='Turn on command verbosity, display jid.'
        )
        self.add_option(
            '-s', '--static',
            default=False,
            action='store_true',
            help='Return the data from minions as a group after they all return.'
        )
        self.add_option(
            '-w', '--wipe',
            default=False,
            action='store_true',
            dest='ssh_wipe',
            help='Remove the deployment of the salt files when done executing.',
        )
        self.add_option(
            '-W', '--rand-thin-dir',
            default=False,
            action='store_true',
            help=('Select a random temp dir to deploy on the remote system. '
                  'The dir will be cleaned after the execution.'))
        self.add_option(
            '-t', '--regen-thin', '--thin',
            dest='regen_thin',
            default=False,
            action='store_true',
            help=('Trigger a thin tarball regeneration. This is needed if '
                  'custom grains/modules/states have been added or updated.'))
        self.add_option(
            '--python2-bin',
            default='python2',
            help='Path to a python2 binary which has salt installed.'
        )
        self.add_option(
            '--python3-bin',
            default='python3',
            help='Path to a python3 binary which has salt installed.'
        )
        self.add_option(
            '--jid',
            default=None,
            help='Pass a JID to be used instead of generating one.'
        )

        ssh_group = optparse.OptionGroup(
            self, 'SSH Options',
            'Parameters for the SSH client.'
        )
        ssh_group.add_option(
            '--remote-port-forwards',
            dest='ssh_remote_port_forwards',
            help='Setup remote port forwarding using the same syntax as with '
                 'the -R parameter of ssh. A comma separated list of port '
                 'forwarding definitions will be translated into multiple '
                 '-R parameters.'
        )
        ssh_group.add_option(
            '--ssh-option',
            dest='ssh_options',
            action='append',
            help='Equivalent to the -o ssh command option. Passes options to '
                 'the SSH client in the format used in the client configuration file. '
                 'Can be used multiple times.'
        )
        self.add_option_group(ssh_group)

        auth_group = optparse.OptionGroup(
            self, 'Authentication Options',
            'Parameters affecting authentication.'
        )
        auth_group.add_option(
            '--priv',
            dest='ssh_priv',
            help='Ssh private key file.'
        )
        auth_group.add_option(
            '--priv-passwd',
            dest='ssh_priv_passwd',
            default='',
            help='Passphrase for ssh private key file.'
        )
        auth_group.add_option(
            '-i',
            '--ignore-host-keys',
            dest='ignore_host_keys',
            default=False,
            action='store_true',
            help='By default ssh host keys are honored and connections will '
                 'ask for approval. Use this option to disable '
                 'StrictHostKeyChecking.'
        )
        auth_group.add_option(
            '--no-host-keys',
            dest='no_host_keys',
            default=False,
            action='store_true',
            help='Removes all host key checking functionality from SSH session.'
        )
        auth_group.add_option(
            '--user',
            dest='ssh_user',
            default='root',
            help='Set the default user to attempt to use when '
                 'authenticating.'
        )
        auth_group.add_option(
            '--passwd',
            dest='ssh_passwd',
            default='',
            help='Set the default password to attempt to use when '
                 'authenticating.'
        )
        auth_group.add_option(
            '--askpass',
            dest='ssh_askpass',
            default=False,
            action='store_true',
            help='Interactively ask for the SSH password with no echo - avoids '
                 'password in process args and stored in history.'
        )
        auth_group.add_option(
            '--key-deploy',
            dest='ssh_key_deploy',
            default=False,
            action='store_true',
            help='Set this flag to attempt to deploy the authorized ssh key '
                 'with all minions. This combined with --passwd can make '
                 'initial deployment of keys very fast and easy.'
        )
        auth_group.add_option(
            '--identities-only',
            dest='ssh_identities_only',
            default=False,
            action='store_true',
            help='Use the only authentication identity files configured in the '
                 'ssh_config files. See IdentitiesOnly flag in man ssh_config.'
        )
        auth_group.add_option(
            '--sudo',
            dest='ssh_sudo',
            default=False,
            action='store_true',
            help='Run command via sudo.'
        )
        auth_group.add_option(
            '--update-roster',
            dest='ssh_update_roster',
            default=False,
            action='store_true',
            help='If hostname is not found in the roster, store the information'
                 'into the default roster file (flat).'
        )
        auth_group.add_option(
            '--pki-dir',
            dest="pki_dir",
            help=("Set the directory to load the pki keys.")
        )
        self.add_option_group(auth_group)

        scan_group = optparse.OptionGroup(
            self, 'Scan Roster Options',
            'Parameters affecting scan roster.'
        )
        scan_group.add_option(
            '--scan-ports',
            default='22',
            dest='ssh_scan_ports',
            help='Comma-separated list of ports to scan in the scan roster.',
        )
        scan_group.add_option(
            '--scan-timeout',
            default=0.01,
            dest='ssh_scan_timeout',
            help='Scanning socket timeout for the scan roster.',
        )
        self.add_option_group(scan_group)

    def _mixin_after_parsed(self):
        if not self.args:
            self.print_help()
            self.error('Insufficient arguments')

        if self.options.list:
            if ',' in self.args[0]:
                self.config['tgt'] = self.args[0].split(',')
            else:
                self.config['tgt'] = self.args[0].split()
        else:
            self.config['tgt'] = self.args[0]

        self.config['argv'] = self.args[1:]
        if not self.config['argv'] or not self.config['tgt']:
            self.print_help()
            self.error('Insufficient arguments')

        # Add back the --no-parse options so that shimmed/wrapped commands
        # handle the arguments correctly.
        if self.options.no_parse:
            self.config['argv'].append(
                '--no-parse=' + ','.join(self.options.no_parse))

        if self.options.ssh_askpass:
            self.options.ssh_passwd = getpass.getpass('Password: ')
            for group in self.option_groups:
                for option in group.option_list:
                    if option.dest == 'ssh_passwd':
                        option.explicit = True
                        break

    def setup_config(self):
        return config.master_config(self.get_config_file_path())

    def process_jid(self):
        if self.options.jid is not None:
            if not salt.utils.jid.is_jid(self.options.jid):
                self.error('\'{0}\' is not a valid JID'.format(self.options.jid))


class SaltCloudParser(six.with_metaclass(OptionParserMeta,
                                         OptionParser,
                                         LogLevelMixIn,
                                         MergeConfigMixIn,
                                         OutputOptionsMixIn,
                                         ConfigDirMixIn,
                                         CloudQueriesMixIn,
                                         ExecutionOptionsMixIn,
                                         CloudProvidersListsMixIn,
                                         CloudCredentialsMixIn,
                                         HardCrashMixin,
                                         SaltfileMixIn)):

    description = (
        'Salt Cloud is the system used to provision virtual machines on various public\n'
        'clouds via a cleanly controlled profile and mapping system'
    )

    usage = '%prog [options] <-m MAP | -p PROFILE> <NAME> [NAME2 ...]'

    # ConfigDirMixIn attributes
    _config_filename_ = 'cloud'

    # LogLevelMixIn attributes
    _default_logging_level_ = config.DEFAULT_CLOUD_OPTS['log_level']
    _default_logging_logfile_ = config.DEFAULT_CLOUD_OPTS['log_file']

    def print_versions_report(self, file=sys.stdout):  # pylint: disable=redefined-builtin
        print('\n'.join(version.versions_report(include_salt_cloud=True)),
              file=file)
        self.exit(salt.defaults.exitcodes.EX_OK)

    def parse_args(self, args=None, values=None):
        try:
            # Late import in order not to break setup
            from salt.cloud import libcloudfuncs
            libcloudfuncs.check_libcloud_version()
        except ImportError as exc:
            self.error(exc)
        return super(SaltCloudParser, self).parse_args(args, values)

    def _mixin_after_parsed(self):
        if 'DUMP_SALT_CLOUD_CONFIG' in os.environ:
            import pprint

            print('Salt Cloud configuration dump (INCLUDES SENSIBLE DATA):')
            pprint.pprint(self.config)
            self.exit(salt.defaults.exitcodes.EX_OK)

        if self.args:
            self.config['names'] = self.args

    def setup_config(self):
        try:
            return config.cloud_config(self.get_config_file_path())
        except salt.exceptions.SaltCloudConfigError as exc:
            self.error(exc)


class SPMParser(six.with_metaclass(OptionParserMeta,
                                   OptionParser,
                                   ConfigDirMixIn,
                                   LogLevelMixIn,
                                   MergeConfigMixIn,
                                   SaltfileMixIn)):
    '''
    The CLI parser object used to fire up the Salt SPM system.
    '''
    description = 'SPM is used to manage 3rd party formulas and other Salt components'

    usage = '%prog [options] <function> <argument>'

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'spm'
    # LogLevelMixIn attributes
    _logfile_config_setting_name_ = 'spm_logfile'
    _default_logging_logfile_ = config.DEFAULT_SPM_OPTS[_logfile_config_setting_name_]

    def _mixin_setup(self):
        self.add_option(
            '-y', '--assume-yes',
            default=False,
            action='store_true',
            help='Default "yes" in answer to all confirmation questions.'
        )
        self.add_option(
            '-f', '--force',
            default=False,
            action='store_true',
            help='Default "yes" in answer to all confirmation questions.'
        )
        self.add_option(
            '-v', '--verbose',
            default=False,
            action='store_true',
            help='Display more detailed information.'
        )

    def _mixin_after_parsed(self):
        # spm needs arguments
        if len(self.args) <= 1:
            if not self.args or self.args[0] not in ('update_repo',):
                self.print_help()
                self.error('Insufficient arguments')

    def setup_config(self):
        return salt.config.spm_config(self.get_config_file_path())


class SaltAPIParser(six.with_metaclass(OptionParserMeta,
                                       OptionParser,
                                       ConfigDirMixIn,
                                       LogLevelMixIn,
                                       DaemonMixIn,
                                       MergeConfigMixIn)):
    '''
    The CLI parser object used to fire up the Salt API system.
    '''
    description = (
        'The Salt API system manages network API connectors for the Salt Master'
    )

    # ConfigDirMixIn config filename attribute
    _config_filename_ = 'master'
    # LogLevelMixIn attributes
    _logfile_config_setting_name_ = 'api_logfile'
    _default_logging_logfile_ = config.DEFAULT_API_OPTS[_logfile_config_setting_name_]

    def setup_config(self):
        return salt.config.api_config(self.get_config_file_path())  # pylint: disable=no-member
