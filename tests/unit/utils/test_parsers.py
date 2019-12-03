# -*- coding: utf-8 -*-
'''
    :codeauthor: Denys Havrysh <denys.gavrysh@gmail.com>
'''

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals
import os
import shutil
import tempfile
# Import Salt Testing Libs
from tests.support.unit import skipIf, TestCase
from tests.support.runtests import RUNTIME_VARS
from tests.support.mock import (
    MagicMock,
    patch,
    NO_MOCK,
    NO_MOCK_REASON
)

# Import Salt Libs
import salt.log.setup as log
import salt.config
import salt.syspaths
import salt.utils.parsers
import salt.utils.platform

try:
    import pytest
except ImportError:
    pytest = None


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
        import multiprocessing
        return multiprocessing.Queue()

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


class ParserBase(object):
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

    @classmethod
    def setUpClass(cls):
        cls.root_dir = tempfile.mkdtemp(dir=RUNTIME_VARS.TMP)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root_dir, ignore_errors=True)

    def setup_log(self):
        '''
        Mock logger functions
        '''
        testing_config = self.default_config.copy()
        testing_config['root_dir'] = self.root_dir
        for name in ('pki_dir', 'cachedir'):
            testing_config[name] = name
        testing_config[self.logfile_config_setting_name] = getattr(self, self.logfile_config_setting_name, self.log_file)
        self.testing_config = testing_config
        self.addCleanup(setattr, self, 'testing_config', None)
        self.log_setup = LogSetupMock()
        patcher = patch.multiple(
            log,
            setup_console_logger=self.log_setup.setup_console_logger,
            setup_extended_logging=self.log_setup.setup_extended_logging,
            setup_logfile_logger=self.log_setup.setup_logfile_logger,
            get_multiprocessing_logging_queue=self.log_setup.get_multiprocessing_logging_queue,
            setup_multiprocessing_logging_listener=self.log_setup.setup_multiprocessing_logging_listener,
            setup_temp_logger=self.log_setup.setup_temp_logger
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(setattr, self, 'log_setup', None)

    # log level configuration tests

    def test_get_log_level_cli(self):
        '''
        Tests that log level match command-line specified value
        '''
        # Set defaults
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

        # Set log level in CLI
        log_level = 'critical'
        args = ['--log-level', log_level] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
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
        opts = self.testing_config.copy()
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
        log_level = default_log_level = self.testing_config[self.loglevel_config_setting_name]

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
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
        log_level = self.testing_config[self.loglevel_config_setting_name]

        # Set log file in CLI
        log_file = '{0}_cli.log'.format(self.log_file)
        args = ['--log-file', log_file] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
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
        log_level = self.testing_config[self.loglevel_config_setting_name]

        args = self.args

        # Set log file in config
        log_file = '{0}_config.log'.format(self.log_file)
        opts = self.testing_config.copy()
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
        log_level = self.testing_config[self.loglevel_config_setting_name]
        log_file = self.testing_config[self.logfile_config_setting_name]
        default_log_file = self.default_config[self.logfile_config_setting_name]

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
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
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

        # Set log file level in CLI
        log_level_logfile = 'error'
        args = ['--log-file-level', log_level_logfile] + self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
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
        log_level = self.testing_config[self.loglevel_config_setting_name]

        args = self.args

        # Set log file level in config
        log_level_logfile = 'info'
        opts = self.testing_config.copy()
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
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

        log_level = default_log_level
        log_level_logfile = default_log_level

        args = self.args

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=self.testing_config)):
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

        opts = self.testing_config.copy()
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

    @skipIf(salt.utils.platform.is_windows(), 'Windows uses a logging listener')
    def test_log_created(self):
        '''
        Tests that log file is created
        '''
        args = self.args
        log_file = self.log_file
        log_file_name = self.logfile_config_setting_name
        opts = self.testing_config.copy()
        opts.update({'log_file': log_file})
        if log_file_name != 'log_file':
            opts.update({log_file_name: getattr(self, log_file_name)})

        if log_file_name == 'key_logfile':
            self.skipTest('salt-key creates log file outside of parse_args.')

        parser = self.parser()
        with patch(self.config_func, MagicMock(return_value=opts)):
            parser.parse_args(args)

        if log_file_name == 'log_file':
            self.assertEqual(os.path.getsize(log_file), 0)
        else:
            self.assertEqual(os.path.getsize(getattr(self, log_file_name)), 0)

    def test_callbacks_uniqueness(self):
        '''
        Test that the callbacks are only added once, no matter
        how many instances of the parser we create
        '''
        mixin_container_names = ('_mixin_setup_funcs',
                                 '_mixin_process_funcs',
                                 '_mixin_after_parsed_funcs',
                                 '_mixin_before_exit_funcs')
        parser = self.parser()
        nums_1 = {}
        for cb_container in mixin_container_names:
            obj = getattr(parser, cb_container)
            nums_1[cb_container] = len(obj)

        # The next time we instantiate the parser, the counts should be equal
        parser = self.parser()
        nums_2 = {}
        for cb_container in mixin_container_names:
            obj = getattr(parser, cb_container)
            nums_2[cb_container] = len(obj)
        self.assertDictEqual(nums_1, nums_2)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(salt.utils.platform.is_windows(), 'Windows uses a logging listener')
class MasterOptionParserTestCase(ParserBase, TestCase):
    '''
    Tests parsing Salt Master options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set defaults
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_master_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.MasterOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(salt.utils.platform.is_windows(), 'Windows uses a logging listener')
class MinionOptionParserTestCase(ParserBase, TestCase):
    '''
    Tests parsing Salt Minion options
    '''
    def setUp(self):
        '''
        Setting up
        '''
        # Set defaults
        self.default_config = salt.config.DEFAULT_MINION_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_minion_parser_test'
        # Function to patch
        self.config_func = 'salt.config.minion_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.MinionOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class ProxyMinionOptionParserTestCase(ParserBase, TestCase):
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
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_proxy_minion_parser_test'
        # Function to patch
        self.config_func = 'salt.config.proxy_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.ProxyMinionOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
@skipIf(salt.utils.platform.is_windows(), 'Windows uses a logging listener')
class SyndicOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_syndic_parser_test'
        self.syndic_log_file = '/tmp/salt_syndic_log'
        # Function to patch
        self.config_func = 'salt.config.syndic_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SyndicOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
        if os.path.exists(self.syndic_log_file):
            os.unlink(self.syndic_log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCMDOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_cmd_parser_test'
        # Function to patch
        self.config_func = 'salt.config.client_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCMDOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCPOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_cp_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCPOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltKeyOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_key_parser_test'
        self.key_logfile = '/tmp/key_logfile'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltKeyOptionParser
        self.addCleanup(delattr, self, 'parser')

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
                'log_datefmt_logfile': None,
                'log_rotate_max_bytes': None,
                'log_rotate_backup_count': None}

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
        default_log_level = self.testing_config[self.loglevel_config_setting_name]

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

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
        if os.path.exists(self.key_logfile):
            os.unlink(self.key_logfile)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCallOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MINION_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_call_parser_test'
        # Function to patch
        self.config_func = 'salt.config.minion_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCallOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltRunOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_run_parser_test'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltRunOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltSSHOptionParserTestCase(ParserBase, TestCase):
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
        self.default_config = salt.config.DEFAULT_MASTER_OPTS.copy()
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_ssh_parser_test'
        self.ssh_log_file = '/tmp/ssh_logfile'
        # Function to patch
        self.config_func = 'salt.config.master_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltSSHOptionParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
        if os.path.exists(self.ssh_log_file):
            os.unlink(self.ssh_log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltCloudParserTestCase(ParserBase, TestCase):
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
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_cloud_parser_test'
        # Function to patch
        self.config_func = 'salt.config.cloud_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltCloudParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SPMParserTestCase(ParserBase, TestCase):
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
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/spm_parser_test'
        self.spm_logfile = '/tmp/spm_logfile'
        # Function to patch
        self.config_func = 'salt.config.spm_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SPMParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
        if os.path.exists(self.spm_logfile):
            os.unlink(self.spm_logfile)


@skipIf(NO_MOCK, NO_MOCK_REASON)
class SaltAPIParserTestCase(ParserBase, TestCase):
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
        self.addCleanup(delattr, self, 'default_config')

        # Log file
        self.log_file = '/tmp/salt_api_parser_test'
        self.api_logfile = '/tmp/api_logfile'
        # Function to patch
        self.config_func = 'salt.config.api_config'

        # Mock log setup
        self.setup_log()

        # Assign parser
        self.parser = salt.utils.parsers.SaltAPIParser
        self.addCleanup(delattr, self, 'parser')

    def tearDown(self):
        if os.path.exists(self.log_file):
            os.unlink(self.log_file)
        if os.path.exists(self.api_logfile):
            os.unlink(self.api_logfile)


@skipIf(not pytest, False)
@skipIf(NO_MOCK, NO_MOCK_REASON)
class DaemonMixInTestCase(TestCase):
    '''
    Tests the PIDfile deletion in the DaemonMixIn.
    '''

    def setUp(self):
        '''
        Setting up
        '''
        # Setup mixin
        self.daemon_mixin = salt.utils.parsers.DaemonMixIn()
        self.daemon_mixin.config = {}
        self.daemon_mixin.config['pidfile'] = '/some/fake.pid'

    def tearDown(self):
        '''
        Tear down test
        :return:
        '''
        del self.daemon_mixin

    @patch('os.unlink', MagicMock())
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('salt.utils.parsers.logger', MagicMock())
    def test_pid_file_deletion(self):
        '''
        PIDfile deletion without exception.
        '''
        self.daemon_mixin._mixin_before_exit()
        assert salt.utils.parsers.os.unlink.call_count == 1
        salt.utils.parsers.logger.info.assert_not_called()
        salt.utils.parsers.logger.debug.assert_not_called()

    @patch('os.unlink', MagicMock(side_effect=OSError()))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('salt.utils.parsers.logger', MagicMock())
    def test_pid_deleted_oserror_as_root(self):
        '''
        PIDfile deletion with exception, running as root.
        '''
        if salt.utils.platform.is_windows():
            patch_args = ('salt.utils.win_functions.is_admin',
                          MagicMock(return_value=True))
        else:
            patch_args = ('os.getuid', MagicMock(return_value=0))

        with patch(*patch_args):
            self.daemon_mixin._mixin_before_exit()
            assert salt.utils.parsers.os.unlink.call_count == 1
            salt.utils.parsers.logger.info.assert_called_with(
                'PIDfile could not be deleted: %s',
                format(self.daemon_mixin.config['pidfile'])
            )
            salt.utils.parsers.logger.debug.assert_called()

    @patch('os.unlink', MagicMock(side_effect=OSError()))
    @patch('os.path.isfile', MagicMock(return_value=True))
    @patch('salt.utils.parsers.logger', MagicMock())
    def test_pid_deleted_oserror_as_non_root(self):
        '''
        PIDfile deletion with exception, running as non-root.
        '''
        if salt.utils.platform.is_windows():
            patch_args = ('salt.utils.win_functions.is_admin',
                          MagicMock(return_value=False))
        else:
            patch_args = ('os.getuid', MagicMock(return_value=1000))

        with patch(*patch_args):
            self.daemon_mixin._mixin_before_exit()
            assert salt.utils.parsers.os.unlink.call_count == 1
            salt.utils.parsers.logger.info.assert_not_called()
            salt.utils.parsers.logger.debug.assert_not_called()
