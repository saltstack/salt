# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Denys Havrysh <denys.gavrysh@gmail.com>`
'''

# Import python libs
from __future__ import absolute_import

# Import Salt Testing Libs
from salttesting import skipIf, TestCase
from salttesting.helpers import ensure_in_syspath
from salttesting.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.utils.parsers
import salt.log.setup as log
import salt.config
import salt.syspaths

ensure_in_syspath('../../')


class ErrorMock(object):  # pylint: disable=too-few-public-methods
    '''
    Error handling
    '''
    def __init__(self):
        '''
        init
        '''
        self.msg = None

    def error(self, msg):
        '''
        Capture error message
        '''
        self.msg = msg


class LogSetupMock(object):
    '''
    Logger setup
    '''
    def __init__(self):
        '''
        init
        '''
        self.log_level = None
        self.log_file = None
        self.log_level_logfile = None
        self.config = {}
        self.temp_log_level = None

    def setup_console_logger(self, log_level='error', **kwargs):  # pylint: disable=unused-argument
        '''
        Set console loglevel
        '''
        self.log_level = log_level

    def setup_extended_logging(self, opts):
        '''
        Set opts
        '''
        self.config = opts

    def setup_logfile_logger(self, logfile, loglevel, **kwargs):  # pylint: disable=unused-argument
        '''
        Set logfile and loglevel
        '''
        self.log_file = logfile
        self.log_level_logfile = loglevel

    @staticmethod
    def get_multiprocessing_logging_queue():  # pylint: disable=invalid-name
        '''
        Mock
        '''
        return None

    def setup_multiprocessing_logging_listener(self, opts, *args):  # pylint: disable=invalid-name,unused-argument
        '''
        Set opts
        '''
        self.config = opts

    def setup_temp_logger(self, log_level='error'):
        '''
        Set temp loglevel
        '''
        self.temp_log_level = log_level


class ObjectView(object):  # pylint: disable=too-few-public-methods
    '''
    Dict object view
    '''
    def __init__(self, d):
        self.__dict__ = d


class LogSettingsParserTests(TestCase):
    '''
    Unit Tests for Log Level Mixin with Salt parsers
    '''
    args = []

    skip_console_logging_config = False

    log_setup = None

    # Set config option names
    loglevel_config_setting_name = 'log_level'
    logfile_config_setting_name = 'log_file'
    logfile_loglevel_config_setting_name = 'log_level_logfile'  # pylint: disable=invalid-name

    def setup_log(self):
        '''
        Mock logger functions
        '''
        self.log_setup = LogSetupMock()
        log.setup_console_logger = self.log_setup.setup_console_logger
        log.setup_extended_logging = self.log_setup.setup_extended_logging
        log.setup_logfile_logger = self.log_setup.setup_logfile_logger
        log.get_multiprocessing_logging_queue = \
                self.log_setup.get_multiprocessing_logging_queue
        log.setup_multiprocessing_logging_listener = \
                self.log_setup.setup_multiprocessing_logging_listener
        log.setup_temp_logger = self.log_setup.setup_temp_logger

    # log level configuration tests

    def test_get_log_level_cli(self):
        '''
        Tests that log level match command-line specified value
        '''
        # Set defaults
        default_log_level = self.default_config[self.loglevel_config_setting_name]

        # Set log level in CLI
        log_level = 'critical'
        args = ['--log-level', log_level] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.default_config)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        console_log_level = getattr(parser.options, self.loglevel_config_setting_name)

        # Check console log level setting
        self.assertEqual(console_log_level, log_level)
        # Check console loggger log level
        self.assertEqual(self.log_setup.log_level, log_level)
        self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                         log_level)
        self.assertEqual(self.log_setup.temp_log_level, log_level)
        # Check log file logger log level
        self.assertEqual(self.log_setup.log_level_logfile, default_log_level)

    def test_get_log_level_config(self):
        '''
        Tests that log level match the configured value
        '''
        args = self.args

        # Set log level in config
        log_level = 'info'
        opts = self.default_config.copy()
        opts.update({self.loglevel_config_setting_name: log_level})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        console_log_level = getattr(parser.options, self.loglevel_config_setting_name)

        # Check console log level setting
        self.assertEqual(console_log_level, log_level)
        # Check console loggger log level
        self.assertEqual(self.log_setup.log_level, log_level)
        self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                         log_level)
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file logger log level
        self.assertEqual(self.log_setup.log_level_logfile, log_level)

    def test_get_log_level_default(self):
        '''
        Tests that log level match the default value
        '''
        # Set defaults
        log_level = default_log_level = self.default_config[self.loglevel_config_setting_name]

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.default_config)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        console_log_level = getattr(parser.options, self.loglevel_config_setting_name)

        # Check log level setting
        self.assertEqual(console_log_level, log_level)
        # Check console loggger log level
        self.assertEqual(self.log_setup.log_level, log_level)
        # Check extended logger
        self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                         log_level)
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file logger
        self.assertEqual(self.log_setup.log_level_logfile, default_log_level)
        # Check help message
        self.assertIn('Default: \'{0}\'.'.format(default_log_level),
                      parser.get_option('--log-level').help)

    # log file configuration tests

    def test_get_log_file_cli(self):
        '''
        Tests that log file match command-line specified value
        '''
        # Set defaults
        log_level = self.default_config[self.loglevel_config_setting_name]

        # Set log file in CLI
        log_file = '{0}_cli.log'.format(self.log_file)
        args = ['--log-file', log_file] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.default_config)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_file_option = getattr(parser.options, self.logfile_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             log_level)
            self.assertEqual(self.log_setup.config[self.logfile_config_setting_name],
                             log_file)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file setting
        self.assertEqual(log_file_option, log_file)
        # Check log file logger
        self.assertEqual(self.log_setup.log_file, log_file)

    def test_get_log_file_config(self):
        '''
        Tests that log file match the configured value
        '''
        # Set defaults
        log_level = self.default_config[self.loglevel_config_setting_name]

        args = self.args

        # Set log file in config
        log_file = '{0}_config.log'.format(self.log_file)
        opts = self.default_config.copy()
        opts.update({self.logfile_config_setting_name: log_file})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_file_option = getattr(parser.options, self.logfile_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             log_level)
            self.assertEqual(self.log_setup.config[self.logfile_config_setting_name],
                             log_file)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file setting
        self.assertEqual(log_file_option, log_file)
        # Check log file logger
        self.assertEqual(self.log_setup.log_file, log_file)

    def test_get_log_file_default(self):
        '''
        Tests that log file match the default value
        '''
        # Set defaults
        log_level = self.default_config[self.loglevel_config_setting_name]
        log_file = default_log_file = self.default_config[self.logfile_config_setting_name]

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.default_config)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_file_option = getattr(parser.options, self.logfile_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             log_level)
            self.assertEqual(self.log_setup.config[self.logfile_config_setting_name],
                             log_file)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file setting
        self.assertEqual(log_file_option, log_file)
        # Check log file logger
        self.assertEqual(self.log_setup.log_file, log_file)
       # Check help message
        self.assertIn('Default: \'{0}\'.'.format(default_log_file),
                      parser.get_option('--log-file').help)

    # log file log level configuration tests

    def test_get_log_file_level_cli(self):
        '''
        Tests that file log level match command-line specified value
        '''
        # Set defaults
        default_log_level = self.default_config[self.loglevel_config_setting_name]

        # Set log file level in CLI
        log_level_logfile = 'error'
        args = ['--log-file-level', log_level_logfile] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.default_config)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_level_logfile_option = getattr(parser.options,
                                           self.logfile_loglevel_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, default_log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             default_log_level)
            self.assertEqual(self.log_setup.config[self.logfile_loglevel_config_setting_name],
                             log_level_logfile)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_setup.log_level_logfile, log_level_logfile)

    def test_get_log_file_level_config(self):
        '''
        Tests that log file level match the configured value
        '''
        # Set defaults
        log_level = self.default_config[self.loglevel_config_setting_name]

        args = self.args

        # Set log file level in config
        log_level_logfile = 'info'
        opts = self.default_config.copy()
        opts.update({self.logfile_loglevel_config_setting_name: log_level_logfile})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_level_logfile_option = getattr(parser.options,
                                           self.logfile_loglevel_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             log_level)
            self.assertEqual(self.log_setup.config[self.logfile_loglevel_config_setting_name],
                             log_level_logfile)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_setup.log_level_logfile, log_level_logfile)

    def test_get_log_file_level_default(self):
        '''
        Tests that log file level match the default value
        '''
        # Set defaults
        default_log_level = self.default_config[self.loglevel_config_setting_name]

        log_level = default_log_level
        log_level_logfile = default_log_level

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.default_config)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_level_logfile_option = getattr(parser.options,
                                           self.logfile_loglevel_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             log_level)
            self.assertEqual(self.log_setup.config[self.logfile_loglevel_config_setting_name],
                             log_level_logfile)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_setup.log_level_logfile, log_level_logfile)
        # Check help message
        self.assertIn('Default: \'{0}\'.'.format(default_log_level),
                      parser.get_option('--log-file-level').help)

    def test_get_console_log_level_with_file_log_level(self):  # pylint: disable=invalid-name
        '''
        Tests that both console log level and log file level setting are working together
        '''
        log_level = 'critical'
        log_level_logfile = 'debug'

        args = ['--log-file-level', log_level_logfile] + self.args

        opts = self.default_config.copy()
        opts.update({self.loglevel_config_setting_name: log_level})

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)
        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        log_level_logfile_option = getattr(parser.options,
                                           self.logfile_loglevel_config_setting_name)

        if not self.skip_console_logging_config:
            # Check console loggger
            self.assertEqual(self.log_setup.log_level, log_level)
            # Check extended logger
            self.assertEqual(self.log_setup.config[self.loglevel_config_setting_name],
                             log_level)
            self.assertEqual(self.log_setup.config[self.logfile_loglevel_config_setting_name],
                             log_level_logfile)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file level setting
        self.assertEqual(log_level_logfile_option, log_level_logfile)
        # Check log file logger
        self.assertEqual(self.log_setup.log_level_logfile, log_level_logfile)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MasterOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Master options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_master_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.MasterOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class MinionOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Minion options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS

        # Log file
        self.log_file = '/tmp/salt_minion_parser_test'
        # Function to patch
        self.config_func = 'salt.config.minion_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.MinionOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ProxyMinionOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Proxy Minion options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_PROXY_MINION_OPTS)

        # Log file
        self.log_file = '/tmp/salt_proxy_minion_parser_test'
        # Function to patch
        self.config_func = 'salt.config.minion_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.ProxyMinionOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SyndicOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Syndic options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set config option names
        self.logfile_config_setting_name = 'syndic_log_file'

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_syndic_parser_test'
        # Function to patch
        self.config_func = 'salt.config.syndic_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SyndicOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCMDOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt CLI options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['foo', 'bar.baz']

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_cmd_parser_test'
        # Function to patch
        self.config_func = 'salt.config.client_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCMDOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCPOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing salt-cp options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['foo', 'bar', 'baz']

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_cp_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCPOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltKeyOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing salt-key options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        self.skip_console_logging_config = True

        # Set config option names
        self.logfile_config_setting_name = 'key_logfile'

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_key_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltKeyOptionParser

    # log level configuration tests

    def test_get_log_level_cli(self):
        '''
        Tests that console log level option is not recognized
        '''
        # No console log level will be actually set
        log_level = default_log_level = None

        option = '--log-level'
        args = self.args + [option, 'error']

        parser = self.parser()
        mock_err = ErrorMock()

        with patch('salt.utils.parsers.OptionParser.error', mock_err.error):
            parser.parse_args(args)

        # Check error msg
        self.assertEqual(mock_err.msg, 'no such option: {0}'.format(option))
        # Check console loggger has not been set
        self.assertEqual(self.log_setup.log_level, log_level)
        self.assertNotIn(self.loglevel_config_setting_name, self.log_setup.config)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file logger log level
        self.assertEqual(self.log_setup.log_level_logfile, default_log_level)

    def test_get_log_level_config(self):
        '''
        Tests that log level set in config is ignored
        '''
        log_level = 'info'
        args = self.args

        # Set log level in config and set additional mocked opts keys
        opts = {self.loglevel_config_setting_name: log_level,
                self.logfile_config_setting_name: 'key_logfile',
                'log_fmt_logfile': None,
                'log_datefmt_logfile': None}

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)
            with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
                parser.setup_logfile_logger()

        # Check config name absence in options
        self.assertNotIn(self.loglevel_config_setting_name, parser.options.__dict__)
        # Check console loggger has not been set
        self.assertEqual(self.log_setup.log_level, None)
        self.assertNotIn(self.loglevel_config_setting_name, self.log_setup.config)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file logger log level
        self.assertEqual(self.log_setup.log_level_logfile, log_level)

    def test_get_log_level_default(self):
        '''
        Tests that log level default value is ignored
        '''
        # Set defaults
        default_log_level = self.default_config[self.loglevel_config_setting_name]

        log_level = None
        args = self.args

        parser = self.parser()
        parser.parse_args(args)

        with patch('salt.utils.parsers.is_writeable', MagicMock(return_value=True)):
            parser.setup_logfile_logger()

        # Check config name absence in options
        self.assertNotIn(self.loglevel_config_setting_name, parser.options.__dict__)
        # Check console loggger has not been set
        self.assertEqual(self.log_setup.log_level, log_level)
        self.assertNotIn(self.loglevel_config_setting_name, self.log_setup.config)
        # Check temp logger
        self.assertEqual(self.log_setup.temp_log_level, 'error')
        # Check log file logger log level
        self.assertEqual(self.log_setup.log_level_logfile, default_log_level)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCallOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Minion options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['foo.bar']

        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS

        # Log file
        self.log_file = '/tmp/salt_call_parser_test'
        # Function to patch
        self.config_func = 'salt.config.minion_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCallOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltRunOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Master options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['foo.bar']

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_run_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltRunOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSSHOptionParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Master options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['foo', 'bar.baz']

        # Set config option names
        self.logfile_config_setting_name = 'ssh_log_file'

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS

        # Log file
        self.log_file = '/tmp/salt_ssh_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltSSHOptionParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCloudParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Cloud options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['-p', 'foo', 'bar']

        # Set default configs
        # Cloud configs are merged with master configs in
        # config/__init__.py, so we'll do that here as well
        # As we need the 'user' key later on.
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_CLOUD_OPTS)

        # Log file
        self.log_file = '/tmp/salt_cloud_parser_test'
        # Function to patch
        self.config_func = 'salt.config.cloud_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCloudParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SPMParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Cloud options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = ['foo', 'bar']

        # Set config option names
        self.logfile_config_setting_name = 'spm_logfile'

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_SPM_OPTS)

        # Log file
        self.log_file = '/tmp/spm_parser_test'
        # Function to patch
        self.config_func = 'salt.config.spm_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SPMParser


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltAPIParserTestCase(LogSettingsParserTests):
    '''
    Tests parsing Salt Cloud options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set mandatory CLI options
        self.args = []

        # Set config option names
        self.logfile_config_setting_name = 'api_logfile'

        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.default_config.update(salt.config.DEFAULT_API_OPTS)

        # Log file
        self.log_file = '/tmp/salt_api_parser_test'
        # Function to patch
        self.config_func = 'salt.config.api_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltAPIParser


# Hide the class from unittest framework when it searches for TestCase classes in the module
del LogSettingsParserTests

if __name__ == '__main__':
    from integration import run_tests  # pylint: disable=import-error,wrong-import-position
    run_tests(MasterOptionParserTestCase,
              MinionOptionParserTestCase,
              ProxyMinionOptionParserTestCase,
              SyndicOptionParserTestCase,
              SaltCMDOptionParserTestCase,
              SaltCPOptionParserTestCase,
              SaltKeyOptionParserTestCase,
              SaltCallOptionParserTestCase,
              SaltRunOptionParserTestCase,
              SaltSSHOptionParserTestCase,
              SaltCloudParserTestCase,
              SPMParserTestCase,
              SaltAPIParserTestCase,
              needs_daemon=False)
