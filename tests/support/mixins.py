# -*- coding: utf-8 -*-
'''
    :codeauthor: :email:`Pedro Algarvio (pedro@algarvio.me)`

    =============
    Class Mix-Ins
    =============

    Some reusable class Mixins
'''
# pylint: disable=repr-flag-used-in-string

# Import python libs
from __future__ import absolute_import
import os
import copy
import pprint
import logging
import warnings
import subprocess

# Import Salt Testing Libs
from tests.support.mock import NO_MOCK, NO_MOCK_REASON, patch
from tests.support.paths import CODE_DIR
from tests.support.runtests import RUNTIME_VARS

# Import salt libs
import salt.version

# Import 3rd-party libs
import salt.ext.six as six

log = logging.getLogger(__name__)


class CheckShellBinaryNameAndVersionMixin(object):
    '''
    Simple class mix-in to subclass in companion to :class:`ShellTestCase<tests.support.case.ShellTestCase>` which
    adds a test case to verify proper version report from Salt's CLI tools.
    '''

    _call_binary_ = None
    _call_binary_expected_version_ = None

    def test_version_includes_binary_name(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')

        if self._call_binary_expected_version_ is None:
            # Late import
            self._call_binary_expected_version_ = salt.version.__version__

        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(self._call_binary_, out)
        self.assertIn(self._call_binary_expected_version_, out)


class SaltReturnAssertsMixin(object):
    '''
    Mix-in class to add as a companion to the TestCase class or it's subclasses which
    adds test assertions for Salt's return data.

    .. code-block: python

        from tests.support.case import ModuleCase
        from tests.support.mixins import SaltReturnAssertsMixin

        class FooTestCase(ModuleCase, SaltReturnAssertsMixin):

            def test_bar(self):
                ret = self.run_function('publish.publish', ['minion', 'test.ping'])
                self.assertReturnSaltType(ret)
    '''

    def assertReturnSaltType(self, ret):
        try:
            self.assertTrue(isinstance(ret, dict))
        except AssertionError:
            raise AssertionError(
                '{0} is not dict. Salt returned: {1}'.format(
                    type(ret).__name__, ret
                )
            )

    def assertReturnNonEmptySaltType(self, ret):
        self.assertReturnSaltType(ret)
        try:
            self.assertNotEqual(ret, {})
        except AssertionError:
            raise AssertionError(
                '{} is equal to {}. Salt returned an empty dictionary.'
            )

    def __return_valid_keys(self, keys):
        if isinstance(keys, tuple):
            # If it's a tuple, turn it into a list
            keys = list(keys)
        elif isinstance(keys, six.string_types):
            # If it's a basestring , make it a one item list
            keys = [keys]
        elif not isinstance(keys, list):
            # If we've reached here, it's a bad type passed to keys
            raise RuntimeError('The passed keys need to be a list')
        return keys

    def __getWithinSaltReturn(self, ret, keys):
        self.assertReturnNonEmptySaltType(ret)
        keys = self.__return_valid_keys(keys)
        okeys = keys[:]
        for part in six.itervalues(ret):
            try:
                ret_item = part[okeys.pop(0)]
            except (KeyError, TypeError):
                raise AssertionError(
                    'Could not get ret{0} from salt\'s return: {1}'.format(
                        ''.join(['[{0!r}]'.format(k) for k in keys]), part
                    )
                )
            while okeys:
                try:
                    ret_item = ret_item[okeys.pop(0)]
                except (KeyError, TypeError):
                    raise AssertionError(
                        'Could not get ret{0} from salt\'s return: {1}'.format(
                            ''.join(['[{0!r}]'.format(k) for k in keys]), part
                        )
                    )
            return ret_item

    def assertSaltTrueReturn(self, ret):
        try:
            self.assertTrue(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not True. Salt Comment:\n{comment}'.format(
                        **(ret.values()[0])
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned:\n{0}'.format(
                        pprint.pformat(ret)
                    )
                )

    def assertSaltFalseReturn(self, ret):
        try:
            self.assertFalse(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not False. Salt Comment:\n{comment}'.format(
                        **(ret.values()[0])
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned: {0}'.format(ret)
                )

    def assertSaltNoneReturn(self, ret):
        try:
            self.assertIsNone(self.__getWithinSaltReturn(ret, 'result'))
        except AssertionError:
            log.info('Salt Full Return:\n{0}'.format(pprint.pformat(ret)))
            try:
                raise AssertionError(
                    '{result} is not None. Salt Comment:\n{comment}'.format(
                        **(ret.values()[0])
                    )
                )
            except (AttributeError, IndexError):
                raise AssertionError(
                    'Failed to get result. Salt Returned: {0}'.format(ret)
                )

    def assertInSaltComment(self, in_comment, ret):
        return self.assertIn(
            in_comment, self.__getWithinSaltReturn(ret, 'comment')
        )

    def assertNotInSaltComment(self, not_in_comment, ret):
        return self.assertNotIn(
            not_in_comment, self.__getWithinSaltReturn(ret, 'comment')
        )

    def assertSaltCommentRegexpMatches(self, ret, pattern):
        return self.assertInSaltReturnRegexpMatches(ret, pattern, 'comment')

    def assertInSalStatetWarning(self, in_comment, ret):
        return self.assertIn(
            in_comment, self.__getWithinSaltReturn(ret, 'warnings')
        )

    def assertNotInSaltStateWarning(self, not_in_comment, ret):
        return self.assertNotIn(
            not_in_comment, self.__getWithinSaltReturn(ret, 'warnings')
        )

    def assertInSaltReturn(self, item_to_check, ret, keys):
        return self.assertIn(
            item_to_check, self.__getWithinSaltReturn(ret, keys)
        )

    def assertNotInSaltReturn(self, item_to_check, ret, keys):
        return self.assertNotIn(
            item_to_check, self.__getWithinSaltReturn(ret, keys)
        )

    def assertInSaltReturnRegexpMatches(self, ret, pattern, keys=()):
        return self.assertRegexpMatches(
            self.__getWithinSaltReturn(ret, keys), pattern
        )

    def assertSaltStateChangesEqual(self, ret, comparison, keys=()):
        keys = ['changes'] + self.__return_valid_keys(keys)
        return self.assertEqual(
            self.__getWithinSaltReturn(ret, keys), comparison
        )

    def assertSaltStateChangesNotEqual(self, ret, comparison, keys=()):
        keys = ['changes'] + self.__return_valid_keys(keys)
        return self.assertNotEqual(
            self.__getWithinSaltReturn(ret, keys), comparison
        )


class AdaptedConfigurationTestCaseMixin(object):

    __slots__ = ()

    def get_config_dir(self):
        return RUNTIME_VARS.TMP_CONF_DIR

    def get_config_file_path(self, filename):
        return os.path.join(RUNTIME_VARS.TMP_CONF_DIR, filename)

    @property
    def master_opts(self):
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'master_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'RUNTIME_VARS\' from {2!r} and instantiate the master configuration like '
            '\'salt.config.master_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "master"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.master_config(
            self.get_config_file_path('master')
        )

    @property
    def minion_opts(self):
        '''
        Return the options used for the minion
        '''
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'minion_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'RUNTIME_VARS\' from {2!r} and instantiate the minion configuration like '
            '\'salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "minion"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.minion_config(
            self.get_config_file_path('minion')
        )

    @property
    def sub_minion_opts(self):
        '''
        Return the options used for the sub-minion
        '''
        # Late import
        import salt.config

        warnings.warn(
            'Please stop using the \'sub_minion_opts\' attribute in \'{0}.{1}\' and instead '
            'import \'RUNTIME_VARS\' from {2!r} and instantiate the sub-minion configuration like '
            '\'salt.config.minion_config(os.path.join(RUNTIME_VARS.TMP_CONF_DIR, "sub_minion_opts"))\''.format(
                self.__class__.__module__,
                self.__class__.__name__,
                __name__
            ),
            DeprecationWarning,
        )
        return salt.config.minion_config(
            self.get_config_file_path('sub_minion')
        )


class SaltClientTestCaseMixin(AdaptedConfigurationTestCaseMixin):
    '''
    Mix-in class that provides a ``client`` attribute which returns a Salt
    :class:`LocalClient<salt:salt.client.LocalClient>`.

    .. code-block:: python

        class LocalClientTestCase(TestCase, SaltClientTestCaseMixin):

            def test_check_pub_data(self):
                just_minions = {'minions': ['m1', 'm2']}
                jid_no_minions = {'jid': '1234', 'minions': []}
                valid_pub_data = {'minions': ['m1', 'm2'], 'jid': '1234'}

                self.assertRaises(EauthAuthenticationError,
                                  self.client._check_pub_data, None)
                self.assertDictEqual({},
                    self.client._check_pub_data(just_minions),
                    'Did not handle lack of jid correctly')

                self.assertDictEqual(
                    {},
                    self.client._check_pub_data({'jid': '0'}),
                    'Passing JID of zero is not handled gracefully')
    '''
    _salt_client_config_file_name_ = 'master'

    @property
    def client(self):
        # Late import
        import salt.client
        return salt.client.get_local_client(
            self.get_config_file_path(self._salt_client_config_file_name_)
        )


class ShellCaseCommonTestsMixin(CheckShellBinaryNameAndVersionMixin):

    _call_binary_expected_version_ = salt.version.__version__

    def test_salt_with_git_version(self):
        if getattr(self, '_call_binary_', None) is None:
            self.skipTest('\'_call_binary_\' not defined.')
        from salt.utils import which
        from salt.version import __version_info__, SaltStackVersion
        git = which('git')
        if not git:
            self.skipTest('The git binary is not available')

        # Let's get the output of git describe
        process = subprocess.Popen(
            [git, 'describe', '--tags', '--first-parent', '--match', 'v[0-9]*'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            close_fds=True,
            cwd=CODE_DIR
        )
        out, err = process.communicate()
        if process.returncode != 0:
            process = subprocess.Popen(
                [git, 'describe', '--tags', '--match', 'v[0-9]*'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                close_fds=True,
                cwd=CODE_DIR
            )
            out, err = process.communicate()
        if not out:
            self.skipTest(
                'Failed to get the output of \'git describe\'. '
                'Error: \'{0}\''.format(
                    salt.utils.to_str(err)
                )
            )

        parsed_version = SaltStackVersion.parse(out)

        if parsed_version.info < __version_info__:
            self.skipTest(
                'We\'re likely about to release a new version. This test '
                'would fail. Parsed(\'{0}\') < Expected(\'{1}\')'.format(
                    parsed_version.info, __version_info__
                )
            )
        elif parsed_version.info != __version_info__:
            self.skipTest(
                'In order to get the proper salt version with the '
                'git hash you need to update salt\'s local git '
                'tags. Something like: \'git fetch --tags\' or '
                '\'git fetch --tags upstream\' if you followed '
                'salt\'s contribute documentation. The version '
                'string WILL NOT include the git hash.'
            )
        out = '\n'.join(self.run_script(self._call_binary_, '--version'))
        self.assertIn(parsed_version.string, out)


class _FixLoaderModuleMockMixinMroOrder(type):
    '''
    This metaclass will make sure that LoaderModuleMockMixin will always come as the first
    base class in order for LoaderModuleMockMixin.setUp to actually run
    '''
    def __new__(mcs, cls_name, cls_bases, cls_dict):
        if cls_name == 'LoaderModuleMockMixin':
            return super(_FixLoaderModuleMockMixinMroOrder, mcs).__new__(mcs, cls_name, cls_bases, cls_dict)
        bases = list(cls_bases)
        for idx, base in enumerate(bases):
            if base.__name__ == 'LoaderModuleMockMixin':
                bases.insert(0, bases.pop(idx))
                break
        return super(_FixLoaderModuleMockMixinMroOrder, mcs).__new__(mcs, cls_name, tuple(bases), cls_dict)


class LoaderModuleMockMixin(six.with_metaclass(_FixLoaderModuleMockMixinMroOrder, object)):
    def setUp(self):
        loader_module = getattr(self, 'loader_module', None)
        if loader_module is not None:
            if NO_MOCK:
                self.skipTest(NO_MOCK_REASON)

            loader_module_name = loader_module.__name__
            loader_module_globals = getattr(self, 'loader_module_globals', None)
            loader_module_blacklisted_dunders = getattr(self, 'loader_module_blacklisted_dunders', ())
            if loader_module_globals is None:
                loader_module_globals = {}
            elif callable(loader_module_globals):
                loader_module_globals = loader_module_globals()
            else:
                loader_module_globals = copy.deepcopy(loader_module_globals)

            salt_dunders = (
                '__opts__', '__salt__', '__runner__', '__context__', '__utils__',
                '__ext_pillar__', '__thorium__', '__states__', '__serializers__', '__ret__',
                '__grains__', '__pillar__', '__sdb__',
                # Proxy is commented out on purpose since some code in salt expects a NameError
                # and is most of the time not a required dunder
                # '__proxy__'
            )
            for dunder_name in salt_dunders:
                if dunder_name not in loader_module_globals:
                    if dunder_name in loader_module_blacklisted_dunders:
                        continue
                    loader_module_globals[dunder_name] = {}

            for key in loader_module_globals:
                if not hasattr(loader_module, key):
                    if key in salt_dunders:
                        setattr(loader_module, key, {})
                    else:
                        setattr(loader_module, key, None)

            if loader_module_globals:
                patcher = patch.multiple(loader_module_name, **loader_module_globals)
                patcher.start()

                def cleanup(patcher, loader_module_globals):
                    patcher.stop()
                    del loader_module_globals

                self.addCleanup(cleanup, patcher, loader_module_globals)
        super(LoaderModuleMockMixin, self).setUp()
